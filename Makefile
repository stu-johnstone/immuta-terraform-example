.PHONY: init fmt validate workspace plan apply destroy data data-test ci ci-validate ci-plan ci-review

ENVIRONMENT ?= non-prod

# Per-environment settings that are not committed (see environments/).
VAR_FILE = environments/$(ENVIRONMENT).tfvars

# Set AUTO_APPROVE=true to skip the confirmation prompt on apply and destroy.
AUTO_APPROVE ?= false
APPROVE_FLAG = $(if $(filter true,$(AUTO_APPROVE)),-auto-approve)

init:
	terraform init

fmt:
	terraform fmt -recursive

validate: init
	terraform validate

workspace: init
	terraform workspace select $(ENVIRONMENT) 2>/dev/null || \
		terraform workspace new $(ENVIRONMENT)

plan: workspace
	TF_LOG_PROVIDER=DEBUG TF_LOG_PATH=./tf.log terraform plan -var-file=$(VAR_FILE)

apply: workspace
	TF_LOG_PROVIDER=DEBUG TF_LOG_PATH=./tf.log terraform apply -var-file=$(VAR_FILE) $(APPROVE_FLAG) -refresh-only

destroy: workspace
	terraform destroy -var-file=$(VAR_FILE) $(APPROVE_FLAG)

# Demo data (see data/README.md): regenerate the SQL files, and test them.
DATAGEN = uv run --project data/generator

data:
	$(DATAGEN) datagen

data-test:
	$(DATAGEN) pytest data/generator/tests

# Simulated CI/CD pipeline (see README.md). Each target is one stage that a
# real pipeline would run on a pull request; `make ci` runs them in order.
# TICKETS is the directory of approved tickets the change is reviewed against;
# BASE is the git revision the change is compared with (HEAD reviews
# uncommitted changes).
TICKETS ?= tickets
BASE ?= HEAD
CI_DIR = .ci
PIPELINE = python3 cicd/pipeline.py

# Stage 1, no credentials: formatting, the provider's checks of each policy
# document, and that every tag, group and attribute a policy names exists.
ci-validate: validate
	terraform fmt -check
	$(PIPELINE) check

# Stage 2, Immuta credentials: the plan the reviewers approve.
ci-plan: workspace
	mkdir -p $(CI_DIR)
	TF_LOG_PROVIDER=DEBUG TF_LOG_PATH=./tf.log terraform plan -var-file=$(VAR_FILE) -out=$(CI_DIR)/tfplan
	terraform show -no-color $(CI_DIR)/tfplan > $(CI_DIR)/plan.txt

# Stage 3, Dust credentials: AI review of the change against every ticket.
# `make ci` includes the plan from stage 2.
ci-review:
	$(PIPELINE) review --tickets $(TICKETS) --base $(BASE) $(if $(REVIEW_PLAN),--plan $(REVIEW_PLAN))

ci: REVIEW_PLAN = $(CI_DIR)/plan.txt
ci: ci-validate ci-plan ci-review
	@echo "All stages passed. A human approves the change, then: make apply"
