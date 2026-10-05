.PHONY: init fmt validate workspace plan apply

ENVIRONMENT := non-prod

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
	terraform plan

apply: workspace
	terraform apply
