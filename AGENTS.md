# AGENTS.md

## Project Overview

This repository is an example implementation using the `terraform-provider-immuta` Terraform provider.

The provider source repository is:

https://github.com/stu-johnstone/terraform-provider-immuta

The provider repository is currently private.

The purpose of this project is to demonstrate how the Immuta Terraform provider can be used from a Terraform configuration. This is an example project rather than a production infrastructure repository.

The example supports multiple deployment environments, such as `non-prod`, `prod`, or alternatives such as `dev` and `test`.

Only the `non-prod` environment should be implemented and used in this example.

Keep the example intentionally simple and focused on demonstrating provider usage.

## Repository Structure

The project should contain:

- Terraform configuration demonstrating the Immuta provider.
- A simple `README.md` explaining what the example does and how to run it.
- A `Makefile` providing simple wrappers around common Terraform commands.
- Environment configuration for the `non-prod` environment.

Do not introduce unnecessary modules, abstractions, or infrastructure.

## Terraform

Use the `terraform-provider-immuta` Terraform provider.

The example must use the `non-prod` environment only.

Environment naming should be structured so that additional environments could be added later without requiring a significant restructuring of the example.

Do not implement a Terraform backend. Local state is intentional for this example and keeps the setup simple.

Use `terraform fmt` and `terraform validate` when appropriate.

## Makefile

The `Makefile` should provide simple wrappers around common Terraform operations rather than hiding Terraform behaviour.

At minimum, provide convenient targets for operations such as:

- `terraform init`
- `terraform fmt`
- `terraform validate`
- `terraform plan`
- `terraform apply`

Targets should remain simple and predictable.

Avoid complex scripting or orchestration.

Commands must not expose credentials, tokens, passwords, or other secrets in their output.

## Security

No credentials or secrets may be committed to this repository.

Do not add:

- API keys
- access tokens
- passwords
- client secrets
- private keys
- `.tfvars` files containing credentials
- credentials embedded directly in Terraform configuration
- credentials embedded in Makefile targets or shell scripts

Use environment variables or another external credential mechanism when credentials are required to run the example.

Never add commands that intentionally print credentials or sensitive environment variables.

Be particularly careful when adding debugging or logging commands.

Do not use commands such as `env`, `printenv`, or `set` where their output could expose credentials.

## Example Scope

This repository is deliberately an example and should remain small.

Prefer:

- straightforward Terraform
- minimal configuration
- clear naming
- explicit examples
- easy-to-follow commands

Avoid:

- production-grade infrastructure patterns that are irrelevant to the example
- unnecessary modules
- complex CI/CD
- Terraform backends
- secret-management infrastructure
- multiple implemented environments
- unrelated infrastructure

If a change makes the example substantially more complicated, prefer the simpler implementation unless the additional complexity is necessary to demonstrate the provider.

## Verification

Before considering a Terraform change complete:

1. Run `terraform fmt`.
2. Run `terraform validate`.
3. Run `terraform plan` when credentials and the required provider configuration are available.
4. Verify that command output does not expose credentials or secrets.

Do not claim that `terraform plan` or `terraform apply` was successfully run if the required external Immuta credentials or environment are unavailable.

## Documentation

Keep `README.md` concise.

It should explain:

- what the example demonstrates
- prerequisites
- how to configure credentials without committing them
- how to initialise Terraform
- how to run the example
- that the example uses the `non-prod` environment
- that no Terraform backend is configured

Do not duplicate extensive implementation details between `README.md` and this file.
