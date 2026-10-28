# Demo SQL

Short Databricks SQL scripts that show the `DEMO.md` policies working. Run
each one as the persona in its name, in a SQL editor or DBeaver connected as
that persona.

| Script | Persona | Shows |
|---|---|---|
| `01_who_am_i.sql` | Anyone | Who is signed in (service principal ID mapped to a display name) |
| `02_cassandra_gold_access.sql` | Cassandra | Gold access, APAC rows only |
| `03_cassandra_no_raw_access.sql` | Cassandra | No access to bronze (raw) tables |
| `04_cassandra_pii_masked.sql` | Cassandra | Names and dates of birth hashed, other PII redacted |
| `05_brian_business_unit.sql` | Brian | Access follows his `BusinessUnit` attribute |
| `06_alice_gold_only.sql` | Alice | Gold in all regions, PII masked, no silver |

Before running:

- The scripts use the `harbourstone` catalog. Change `USE CATALOG` if the
  data is somewhere else.
- Fill in the service principal application IDs in `01_who_am_i.sql`.
- After an attribute changes (Brian's business unit, Cassandra's PII
  access), give Immuta a moment to update Databricks before re-running.
