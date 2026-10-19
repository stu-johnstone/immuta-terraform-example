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
- Classification frameworks (tag sensitivity and classification rules)
- Databricks, Snowflake and Redshift connections (structured so Trino can be added)
- Data object settings and tags on the registered Harbourstone data
- Dynamic domain assignment by tag
- Global data and subscription policies, one YAML file each in `policies/`

The users, groups, tags and policies implement the demo in `DEMO.md`, using
the Harbourstone Financial data in `data/` (see `data/README.md`):

- **Cassandra** (Analytics group, `Region` APAC) gets the curated tables,
  only the APAC rows, with PII masked. Uncommenting her `PII Access`
  attribute in `locals.tf` plays Brian's approval of unmasked names and
  dates of birth.
- **Brian** gets the tables of his `BusinessUnit`. Change it from
  `Insurance` to `Retail Banking` in `locals.tf` and apply: his access
  changes, the policies do not.
- **Alice** (Executives group) gets the gold tables only, with PII masked.

Load the Databricks data before applying: the Harbourstone schemas and
gold tables are looked up in the connection to tag them.

The configuration is deliberately data-driven. Example domains, users, groups,
tags, identifiers, frameworks and connections are defined in `locals.tf`; each user and group lists its own attributes, and
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

Non-secret settings you do not want to commit, such as connection hosts,
usernames, the Databricks SQL warehouse path, the Snowflake warehouse and role,
and the email of the user who owns connection data objects,
go in a per-environment variables file,
`environments/<environment>.tfvars`. These files are gitignored, and the
Makefile passes the one matching `ENVIRONMENT` with `-var-file`:

    cp environments/non-prod.tfvars.example environments/non-prod.tfvars

Set `harbourstone_catalog` there if the demo data is not in the
`harbourstone` catalog.

Connection secrets are supplied through Terraform variables set from
`TF_VAR_` environment variables:

    export TF_VAR_databricks_token="..."   # Databricks personal access token
    export TF_VAR_redshift_password="..."  # Redshift user's password

Before applying, create the Immuta user on each platform with the connection's
setup script (Snowflake: a user with a key pair, a role and a warehouse;
Redshift: a user with a password).

### Snowflake key pair

Immuta's API does not accept a password or programmatic access token for
Snowflake, so the Immuta user signs in with a key pair. Terraform reads the
private key from a file; it is not an environment variable.

| File | What it is | Used by |
|---|---|---|
| `~/.ssh/immuta_snowflake_key.p8` | Private key: unencrypted PKCS#8 RSA, 2048-bit | Terraform (`snowflake_private_key_file`, which defaults to this path) |
| `~/.ssh/immuta_snowflake_key.pub` | Public key | Snowflake (`ALTER USER ... SET RSA_PUBLIC_KEY`) |

Snowflake only supports RSA keys, so an `id_ed25519` key will not work. Create
the pair and give Snowflake the public key:

    openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -nocrypt -out ~/.ssh/immuta_snowflake_key.p8
    openssl rsa -in ~/.ssh/immuta_snowflake_key.p8 -pubout -out ~/.ssh/immuta_snowflake_key.pub
    chmod 600 ~/.ssh/immuta_snowflake_key.p8

    # The public key as one line, for RSA_PUBLIC_KEY
    grep -v -- '-----' ~/.ssh/immuta_snowflake_key.pub | tr -d '\n'

Then, in Snowflake:

    ALTER USER <immuta user> SET RSA_PUBLIC_KEY = '<that line>';

To keep the key somewhere else, set `snowflake_private_key_file` in
`environments/<environment>.tfvars`. The key ends up in the Terraform state, as
all connection credentials do.

Secrets must never be committed to the repository or printed by scripts.

Connections use `prevent_destroy`, because destroying a connection deletes
every data object registered through it. `make destroy` fails until that is
removed from `connections.tf`.

The Immuta host is non-sensitive configuration and is defined per environment
in `locals.tf`.

## Usage

    make init
    make validate
    make plan
    make apply

`apply` and `destroy` ask for confirmation. Set `AUTO_APPROVE=true` to skip
it, for example `AUTO_APPROVE=true make apply`.

No Terraform backend is configured; state is stored locally for simplicity.

## Project Structure

    .
    ├── AGENTS.md
    ├── Makefile
    ├── README.md
    ├── versions.tf     # Terraform and provider versions
    ├── provider.tf     # Environments and provider configuration
    ├── locals.tf       # Example data
    ├── domains.tf      # Domains, their tag assignment and copied identifiers
    ├── identifiers.tf  # Tags and identifiers
    ├── frameworks.tf   # Classification frameworks
    ├── connections.tf  # Data platform connections and their variables
    ├── data_objects.tf # Settings and tags on the Harbourstone data objects
    ├── policies.tf     # Global policies, one per file in policies/
    ├── policies/       # Global policies in the Immuta V2 policy format (YAML)
    ├── environments/   # <environment>.tfvars settings (gitignored) and templates
    ├── users.tf        # Users and user attributes
    ├── groups.tf       # Groups, group attributes and memberships
    └── outputs.tf      # Outputs
