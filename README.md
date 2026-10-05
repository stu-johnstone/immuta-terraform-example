# Immuta Terraform Provider Example

Example Terraform configuration using the
[`terraform-provider-immuta`](https://github.com/stu-johnstone/terraform-provider-immuta)
provider.

The provider is currently private and this repository is intended as a simple,
working example rather than a production deployment.

## What this demonstrates

The example manages common Immuta resources:

- Domains
- Users
- Groups
- Group memberships
- User and group attributes

The configuration is deliberately data-driven. Example users, groups, domains,
and attributes are defined in `locals.tf` and resources use `for_each`, making it
easy to add additional examples without duplicating Terraform resources.

## Environments

Terraform workspaces represent environments.

`non-prod` is the default and is the only environment required for this example.
The environment configuration, including the Immuta host, is defined in
`locals.tf`.

For example:

    make plan

or explicitly:

    ENVIRONMENT=non-prod make plan

## Credentials

The Immuta API key is supplied through:

    export IMMUTA_API_KEY="..."

The API key must never be committed to the repository or printed by scripts.

The Immuta host is non-sensitive configuration and is defined per environment
in `locals.tf`.

## Usage

    make init
    make validate
    make plan
    make apply

No Terraform backend is configured; state is stored locally for simplicity.

## Project Structure

    .
    ├── AGENTS.md
    ├── Makefile
    ├── README.md
    ├── versions.tf
    ├── provider.tf
    ├── locals.tf
    ├── domains.tf
    ├── groups.tf
    ├── users.tf
    ├── attributes.tf
    └── outputs.tf
