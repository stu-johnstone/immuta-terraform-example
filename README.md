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
- Tags
- Identifiers (regex, column name regex and dictionary)
- Copying reference identifiers into a domain

The configuration is deliberately data-driven. Example domains, users and groups
are defined in `locals.tf`; each user and group lists its own attributes, and
each group lists its members by user key. Resources use `for_each`, so adding an
example means adding an entry to `locals.tf` rather than a new resource.

## Environments

Terraform workspaces represent environments.

`non-prod` is the default and is the only environment required for this example.
The environment configuration, including the Immuta host, is defined in
`provider.tf`.

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
    ├── versions.tf     # Terraform and provider versions
    ├── provider.tf     # Environments and provider configuration
    ├── locals.tf       # Example data
    ├── domains.tf      # Domains and identifiers copied into them
    ├── identifiers.tf  # Tags and identifiers
    ├── users.tf        # Users and user attributes
    ├── groups.tf       # Groups, group attributes and memberships
    └── outputs.tf      # Outputs
