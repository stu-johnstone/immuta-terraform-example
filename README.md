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
- Data and subscription policies, one YAML file each in `policies/`; the
  business unit subscription policies are scoped to their domain, the rest are
  global

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
- **Data Stewards** (an existing SSO user, added by email in `locals.tf`) are
  exempt from the region row filter and see every row. PII is still masked.

Load the Databricks data before applying: the Harbourstone schemas and
gold tables are looked up in the connection to tag them.

The configuration is deliberately data-driven. Example domains, users, groups,
tags, identifiers, frameworks and connections are defined in `locals.tf`; each user and group lists its own attributes, and
each group lists its members by user key. Resources use `for_each`, so adding an
example means adding an entry to `locals.tf` rather than a new resource.

## Entra test users

To play the demo with identities from Microsoft Entra ID, create these test
users and groups in Entra by hand. Terraform does not manage them. They mirror
Cassandra, Brian and Alice. They have different names, user IDs and group names
so that they stay separate from the Terraform-managed users and groups in
`locals.tf`. Everything uses the `DEMO` prefix so that nobody mistakes them for
real Immuta users.

| Entra user (display name, UPN) | Plays | Groups | Attributes |
|---|---|---|---|
| `[DEMO] Diana Shaw`, `demo-diana.shaw@<tenant domain>` | Cassandra (analyst) | `DEMO-Immuta-Analytics`, `DEMO-Immuta-Users` | `Region` APAC. Add `PII Access` "Names and Dates of Birth" when her request is approved |
| `[DEMO] Ethan Brooks`, `demo-ethan.brooks@<tenant domain>` | Brian (manager) | `DEMO-Immuta-Users` | `BusinessUnit` Insurance (change to Retail Banking during the demo), `Region` APAC |
| `[DEMO] Fiona Grant`, `demo-fiona.grant@<tenant domain>` | Alice (CEO) | `DEMO-Immuta-Executives`, `DEMO-Immuta-Users` | `Region` APAC, EMEA and AMER |

- Set Ethan as Diana's manager. In the story, he approves her request.
- Assign only `DEMO-Immuta-Users` to the Immuta enterprise application. Then
  provisioning and sign-in reach only the test users.
- Attribute names must match the policies exactly: `Region`, `BusinessUnit`,
  `PII Access`. `Region` takes more than one value for Fiona. How the
  attributes reach Immuta depends on how the Entra integration is configured.
- The subscription policies match the groups `Analytics` and `Executives` by
  name. They do not match `DEMO-Immuta-Analytics` or `DEMO-Immuta-Executives`
  until those group names are added to `policies/subscription-analytics.yaml`
  and `policies/subscription-executive-insights.yaml`. Attribute-based
  policies (region, business unit, PII access) apply to the Entra users as
  they are.

## Environments

Terraform workspaces represent environments.

`non-prod` is the default and is the only environment required for this example.
Each environment's configuration, including the Immuta host (`immuta_host`),
comes from `environments/<environment>.tfvars` (see Credentials below).

For example:

    make plan

or explicitly:

    ENVIRONMENT=non-prod make plan

## Credentials

The Immuta API key is supplied through:

    export IMMUTA_API_KEY="..."

Non-secret settings you do not want to commit, such as the Immuta host, connection hosts,
usernames, the Databricks SQL warehouse path, the Snowflake warehouse and role,
and the email of the user who owns connection data objects,
go in a per-environment variables file,
`environments/<environment>.tfvars`. These files are gitignored, and the
Makefile passes the one matching `ENVIRONMENT` with `-var-file`:

    cp environments/non-prod.tfvars.example environments/non-prod.tfvars

Set `databricks_catalog` there if the demo data is not in the
`harbourstone` catalog.

Connection secrets are supplied through Terraform variables set from
`TF_VAR_` environment variables:

    export TF_VAR_databricks_token="..."   # Databricks personal access token
    export TF_VAR_redshift_password="..."  # Redshift user's password

Before applying, create the Immuta user on each platform with the connection's
setup script (Snowflake: a user with a key pair, a role and a warehouse;
Redshift: a user with a password).

On Redshift, unlike Snowflake and Databricks, the schemas must exist before
the connection is created. Load the HR data (database `hr`, one schema per
company; see `data/README.md`) before the first `make apply`.

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

## Usage

    make init
    make validate
    make plan
    make apply

`apply` and `destroy` ask for confirmation. Set `AUTO_APPROVE=true` to skip
it, for example `AUTO_APPROVE=true make apply`.

No Terraform backend is configured; state is stored locally for simplicity.

## Simulated CI/CD

Make targets play the stages a pipeline would run on a pull request. The
tickets in `tickets/` are the approved access requests: the `DEMO.md` story
written as Jira-style requests with acceptance criteria. Every ticket should
be implemented. Add a ticket by adding a markdown file.

| Stage | Target | Needs | Checks |
|---|---|---|---|
| 1 | `make ci-validate` | Nothing | `terraform fmt` and `validate` (the provider's checks of each policy document), and that every tag, group and attribute a policy names exists in `locals.tf` |
| 2 | `make ci-plan` | Immuta credentials | The plan, saved in `.ci/` |
| 3 | `make ci-review` | [Ollama](https://ollama.com) running locally (or Dust credentials) | An AI model checks the configuration and policies against every acceptance criterion of every ticket |

The review sends the tickets, the users, groups, attributes and tags, and
every policy to the model, which marks each acceptance criterion `met`,
`not_met` or `unclear`. The pipeline decides the verdict from those: every
criterion met passes, any not met fails, anything else needs a human.

`make ci` runs all three stages. Nothing is applied: a human approves, then
runs `make apply`. Immuta itself fully validates a policy only when it is
applied.

The prompt is `cicd/prompt.md`: edit it to tune the review. Results are saved
in `.ci/review.json`. `make ci-test` runs the pipeline's unit tests.

By default the review uses a local Ollama model, so it needs no credentials:

    ollama pull qwen3-coder:30b      # once
    make ci-review                   # or OLLAMA_MODEL=<model> make ci-review

Set `OLLAMA_HOST` if Ollama is not on `localhost:11434`.

To use a Dust agent instead, run `REVIEW_BACKEND=dust make ci-review` with
these environment variables set:

    export DUST_API_KEY=...          # Dust API key; never commit it
    export DUST_WORKSPACE_ID=...     # from the Dust workspace URL
    export DUST_AGENT_ID=...         # sId of the agent that runs the prompt
    # export DUST_API_URL=https://eu.dust.tt  # for an EU workspace

Use an agent with no tools and no instructions of its own, so the review
depends only on `cicd/prompt.md` and the material.

To demo it, add a ticket, for example `tickets/DEMO-105.md` asking that
Brian is a member of the Executives group, and run `make ci-review`: it fails
because the configuration does not meet it. Make the change in `locals.tf`
and it passes. Delete `policies/data-mask-names-dob.yaml` instead and it
fails, even though stage 1 passes, because PII is no longer masked. Change
`Analytics` to `Analytic` in a policy and stage 1 fails.

## Project Structure

    .
    ├── AGENTS.md
    ├── Makefile
    ├── README.md
    ├── versions.tf     # Terraform and provider versions
    ├── provider.tf     # Provider configuration and the Immuta host variable
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
    ├── outputs.tf      # Outputs
    ├── tickets/        # DEMO.md as Jira-style tickets, for the simulated CI/CD
    └── cicd/           # Simulated CI/CD: policy check and AI review (prompt.md)
