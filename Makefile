.PHONY: init fmt validate workspace plan apply destroy data data-test

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
	terraform plan -var-file=$(VAR_FILE)

apply: workspace
	terraform apply -var-file=$(VAR_FILE) $(APPROVE_FLAG)

destroy: workspace
	terraform destroy -var-file=$(VAR_FILE) $(APPROVE_FLAG)

# Demo data (see data/README.md): regenerate the SQL files, and test them.
DATAGEN = uv run --project data/generator

data:
	$(DATAGEN) datagen

data-test:
	$(DATAGEN) pytest data/generator/tests
