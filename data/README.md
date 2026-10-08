# Demo data

Fictional companies with realistic, connected data for demonstrating Immuta:
discovery and classification, masking, row-level security, frameworks, and
asking questions of governed data with AI. Each company is a separate
business; they all load into one Immuta instance only for ease of
management.

Everything here is made up. See [Is the data safe?](#is-the-data-safe).

## Companies

| Company | Industry | Businesses (schemas) | Status |
|---|---|---|---|
| [Harbourstone Financial Group](harbourstone_financial/README.md) | Financial Services | retail_banking, commercial_banking, insurance | Done |
| Northgrid Utilities | Utilities | energy, water, communications | Planned |
| Vitalis Health Group | Health | health_insurance, hospitals, dental | Planned |
| Forgeline Industries | Manufacturing | production, supply_chain, quality | Planned |

## Where the data lives

Data is split by kind, so only four connectors are needed:

| Platform | Data | Layout |
|---|---|---|
| Databricks | Financial Services and Utilities operational data | catalog per company, schema per business |
| Snowflake | Health and Manufacturing operational data | database per company, schema per business |
| Redshift | HR for every company | database `hr`, schema per company |
| BigQuery | Marketing for every company | dataset `<company>_marketing` |

For example, `harbourstone.commercial_banking.gold_risk_profile` (Databricks),
`hr.harbourstone.silver_employees` (Redshift) and
`harbourstone_marketing.gold_campaign_performance` (BigQuery).

## Folder layout

```
data/
├── README.md
├── generator/                     # Python generator (uv) and its tests
└── <company>/
    ├── README.md                  # The business, its tables and sample questions
    ├── <platform>/<company>.sql   # Operational data (Databricks or Snowflake)
    ├── redshift/<company>_hr.sql
    └── bigquery/<company>_marketing.sql
```

Each `.sql` file is self-contained: paste it into the platform's SQL editor
and run it top to bottom. It creates the catalog, database, schemas or
datasets it needs, then the tables, and can be re-run; tables are replaced
each time. Comments explain every step and every table.

| Platform | Before running |
|---|---|
| Databricks | Needs Unity Catalog and permission to create catalogs. If `CREATE CATALOG` fails because the metastore has no storage root, add `MANAGED LOCATION '<path>'`. |
| Snowflake | Use a role that can create databases and select a warehouse. |
| Redshift | Run `CREATE DATABASE hr;` once, then connect to `hr` and run the file. |
| BigQuery | Select the project in the console. Datasets are created in `australia-southeast1`; change it in the file if needed. |

The Databricks file for a company is about 1.3 MB. If the editor struggles
to paste it, run it as a file instead (for example, import it as a SQL file
or run it with the Databricks CLI).

## Medallion layers

Every business follows the same pattern, with the layer as a table prefix:

- **`bronze_`**: raw extracts from the source systems, loaded as-is. Values
  are messy where real sources are: country spelt `AU`, `AUS` or
  `Australia`; name and status casing varies; some transactions are sent
  twice. Each row records its `_source_system` and `_batch_id`.
- **`silver_`**: built from bronze. Cleaned, typed and conformed: duplicates
  removed, ISO country codes, ages, flags and a `region` column.
- **`gold_`**: built from silver. Business-ready data products for
  reporting and AI: plain column names, AUD amounts and, where useful, the
  latest free-text note or comment so questions can be answered in context.

Only bronze tables are loaded with data; silver and gold are created from
them with `CREATE TABLE ... AS SELECT`, so the SQL also shows the pipeline.

## Regions

Companies are headquartered in Australia, with most data in APAC and some
international (for example Harbourstone's London branch and US-based
customers). Every silver and gold table about people or money has:

- `country`: ISO code (`AU`, `NZ`, `SG`, `GB`, `US`)
- `region`: `APAC`, `EMEA` or `AMER`

so a single "only show rows in your region" rule, using a user's `Region`
attribute, works everywhere.

## Dates

Dates are relative to the day a script runs, so "today", "this month" and
"the last 12 months" always return data. Today's transactions are spread
across the whole day, so some may be later than the current time. Re-run a
script to move the data forward. Dates of birth are fixed.

## Is the data safe?

Yes. People, companies, addresses and identifiers are generated. Where a
reserved or test range exists, it is used:

- Emails use `example.com`, `example.net` and `example.org`.
- IP addresses are in the documentation ranges (`192.0.2.x`, `198.51.100.x`,
  `203.0.113.x`).
- Phone numbers use ranges set aside for fiction (AU `02/03 5550 xxxx`, UK
  `07700 900xxx`, US `555-01xx`); AU mobiles use the `0491 570` block.
- Card numbers are on the `411111` and `555555` test prefixes.

Tax file numbers and ABNs are random but pass their checksums, so Immuta's
discovery recognises them. They are not anyone's real numbers by design, but
treat them as demo data only.

## Generator

The SQL is generated by a small Python project in `generator/`, so tables
and data are defined once and written for each platform. It needs
[uv](https://docs.astral.sh/uv/).

```
make data        # regenerate the SQL files
make data-test   # run the tests
```

The generated files are committed; you only need the generator to change
or add data. Output is deterministic: regenerating without changes produces
identical files.

The tests run every script end to end in DuckDB (so silver and gold only use
columns and tables that exist, and every table has rows), parse each file
with that platform's SQL grammar, and check the committed files are up to
date. They do not run anything on the real platforms.

| Module | What it does |
|---|---|
| `dialects.py` | Everything platform-specific: types, literals, dates, JSON and DDL |
| `render.py` | Writes a script, with comments, for a platform |
| `fake.py` | Deterministic fake names, addresses and identifiers |
| `common.py` | Company profile and shared SQL for country, region and currency |
| `hr.py`, `marketing.py` | HR and marketing data, the same for every company |
| `companies/` | Each company's businesses: bronze data, silver and gold SQL |
