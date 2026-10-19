"""How each platform spells types, literals, dates, JSON and DDL.

Everything platform-specific lives here, so companies write their tables
and transformations once. Derived-table SQL otherwise sticks to syntax all
platforms share: CASE, COALESCE, NULLIF, TRIM, UPPER, LOWER, REGEXP_REPLACE,
ROUND, FLOOR, ||, window functions, GROUP BY ordinals and CTEs.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .model import At, DaysAgo, Script, Table


class Dialect:
    key = ""
    title = ""
    today = "CURRENT_DATE"
    three_part_names = True
    types: dict[str, str] = {}

    # Names and types -------------------------------------------------------

    def table(self, container: str | None, schema: str, name: str) -> str:
        if container and self.three_part_names:
            return f"{container}.{schema}.{name}"
        return f"{schema}.{name}"

    def type(self, logical: str) -> str:
        if logical.startswith("decimal("):
            return self.decimal_type(logical.removeprefix("decimal(").removesuffix(")"))
        return self.types[logical]

    def decimal_type(self, precision_scale: str) -> str:
        return f"DECIMAL({precision_scale})"

    def cast_type(self, logical: str) -> str:
        """The type to use in CAST, which some platforms spell differently."""
        return self.type(logical)

    # Literals ----------------------------------------------------------------

    def literal(self, value) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, Decimal):
            return self.decimal_literal(value)
        if isinstance(value, str):
            return self.string(value)
        if isinstance(value, DaysAgo):
            return self.days_ago(value.days)
        if isinstance(value, At):
            return self.at(value.days_ago, value.minute)
        if isinstance(value, date):
            return f"DATE '{value.isoformat()}'"
        raise TypeError(f"cannot write {value!r} as SQL")

    def decimal_literal(self, value: Decimal) -> str:
        return str(value)

    def string(self, value: str) -> str:
        # Databricks, Snowflake and BigQuery read backslash escapes in strings.
        return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"

    # Dates and JSON ------------------------------------------------------------

    def days_ago(self, days: int) -> str:
        raise NotImplementedError

    def at(self, days_ago: int, minute: int) -> str:
        raise NotImplementedError

    def add_days(self, expr: str, days: int | str) -> str:
        raise NotImplementedError

    def days_between(self, start: str, end: str) -> str:
        raise NotImplementedError

    def month_start(self, expr: str) -> str:
        raise NotImplementedError

    def json_text(self, column: str, key: str) -> str:
        raise NotImplementedError

    def initcap(self, expr: str) -> str:
        return f"INITCAP({expr})"

    # Shared expressions built on the above --------------------------------------

    def age(self, birth_date: str) -> str:
        """Whole years between a birth date and today."""
        return f"CAST(FLOOR({self.days_between(birth_date, self.today)} / 365.25) AS {self.type('int')})"

    def years_between(self, start: str, end: str) -> str:
        return f"ROUND({self.days_between(start, end)} / 365.25, 1)"

    def pct(self, numerator: str, denominator: str) -> str:
        """numerator / denominator as a percentage to 1 decimal place, NULL
        when the denominator is 0. Casts first: Redshift divides integers."""
        return f"ROUND(CAST({numerator} AS {self.cast_type('decimal(18,4)')}) * 100 / NULLIF({denominator}, 0), 1)"

    def money(self, expr: str) -> str:
        return f"CAST({expr} AS {self.type('decimal(18,2)')})"

    # DDL ---------------------------------------------------------------------

    def setup(self, script: Script) -> tuple[list[str], list[str]]:
        """Notes to show and statements to create the containers."""
        raise NotImplementedError

    def column_comment(self, comment: str) -> str:
        return ""

    def table_comment(self, comment: str) -> str:
        return ""

    def create_table(self, name: str, table: Table) -> list[str]:
        columns = ",\n".join(
            f"  {c.name} {self.type(c.type)}{self.column_comment(c.comment) if c.comment else ''}"
            for c in table.columns
        )
        return [f"CREATE OR REPLACE TABLE {name} (\n{columns}\n){self.table_comment(table.comment)};"]

    def insert(self, name: str, table: Table) -> list[str]:
        if not table.rows:
            return []
        columns = ", ".join(c.name for c in table.columns)
        rows = ",\n".join("  (" + ", ".join(self.literal(v) for v in row) + ")" for row in table.rows)
        return [f"INSERT INTO {name} ({columns}) VALUES\n{rows};"]

    def create_table_as(self, name: str, comment: str, select: str) -> list[str]:
        return [f"CREATE OR REPLACE TABLE {name}{self.table_comment(comment)}\nAS\n{select.strip()};"]


class Databricks(Dialect):
    key = "databricks"
    title = "Databricks"
    today = "current_date()"
    # Tables go in the catalog selected when the script runs, so it works in a
    # shared workspace where each person has their own catalog.
    three_part_names = False
    # Shared or built-in catalogs the script refuses to write to.
    protected_catalogs = ("hive_metastore", "main", "samples", "system", "workspace")
    types = {
        "string": "STRING", "text": "STRING", "json": "STRING", "int": "INT", "bigint": "BIGINT",
        "date": "DATE", "timestamp": "TIMESTAMP", "bool": "BOOLEAN",
    }

    def days_ago(self, days: int) -> str:
        if days == 0:
            return "current_date()"
        return f"date_sub(current_date(), {days})" if days > 0 else f"date_add(current_date(), {-days})"

    def at(self, days_ago: int, minute: int) -> str:
        return f"CAST({self.days_ago(days_ago)} AS TIMESTAMP) + INTERVAL {minute} MINUTES"

    def add_days(self, expr: str, days: int | str) -> str:
        return f"date_add({expr}, {days})"

    def days_between(self, start: str, end: str) -> str:
        return f"datediff(CAST({end} AS DATE), CAST({start} AS DATE))"

    def month_start(self, expr: str) -> str:
        return f"CAST(date_trunc('MONTH', {expr}) AS DATE)"

    def json_text(self, column: str, key: str) -> str:
        return f"get_json_object({column}, '$.{key}')"

    def setup(self, script: Script) -> tuple[list[str], list[str]]:
        notes = [
            "Needs Unity Catalog. Tables are created in the current catalog: select",
            "your own catalog first (the catalog picker in the SQL editor or DBeaver,",
            f"or USE CATALOG <your catalog>), for example {script.container}. The first",
            "statement stops the script if a shared or built-in catalog is selected.",
        ]
        protected = ", ".join(self.string(c) for c in self.protected_catalogs)
        statements = [
            f"SELECT assert_true(current_catalog() NOT IN ({protected}),\n"
            f"  'Select your own catalog (USE CATALOG <your catalog>) before running this script.');"
        ]
        statements += [
            f"CREATE SCHEMA IF NOT EXISTS {s.name}{self.table_comment(s.title)};" for s in script.schemas
        ]
        return notes, statements

    def column_comment(self, comment: str) -> str:
        return f" COMMENT {self.string(comment)}"

    def table_comment(self, comment: str) -> str:
        return f"\nCOMMENT {self.string(comment)}"


class Snowflake(Dialect):
    key = "snowflake"
    title = "Snowflake"
    # Tables go in the database selected when the script runs, so it works in
    # a shared account where each person has their own database.
    three_part_names = False
    types = {
        "string": "VARCHAR", "text": "VARCHAR", "json": "VARCHAR", "int": "INT", "bigint": "BIGINT",
        "date": "DATE", "timestamp": "TIMESTAMP_NTZ", "bool": "BOOLEAN",
    }

    def decimal_type(self, precision_scale: str) -> str:
        return f"NUMBER({precision_scale})"

    def days_ago(self, days: int) -> str:
        return "CURRENT_DATE" if days == 0 else f"DATEADD(day, {-days}, CURRENT_DATE)"

    def at(self, days_ago: int, minute: int) -> str:
        return f"DATEADD(minute, {minute}, CAST({self.days_ago(days_ago)} AS TIMESTAMP_NTZ))"

    def add_days(self, expr: str, days: int | str) -> str:
        return f"DATEADD(day, {days}, {expr})"

    def days_between(self, start: str, end: str) -> str:
        return f"DATEDIFF(day, CAST({start} AS DATE), CAST({end} AS DATE))"

    def month_start(self, expr: str) -> str:
        return f"CAST(DATE_TRUNC('MONTH', {expr}) AS DATE)"

    def json_text(self, column: str, key: str) -> str:
        return f"JSON_EXTRACT_PATH_TEXT({column}, '{key}')"

    def setup(self, script: Script) -> tuple[list[str], list[str]]:
        notes = [
            "Tables are created in the current database: select your own database",
            "first (the database picker in the worksheet or DBeaver, or",
            f"USE DATABASE <your database>), for example {script.container}. Snowflake stops",
            "the script if no database is selected. Needs a role that can create",
            "schemas in it and a warehouse (USE WAREHOUSE <your warehouse>).",
            "Unquoted names are stored in upper case.",
        ]
        statements = [f"CREATE SCHEMA IF NOT EXISTS {s.name}{self.table_comment(s.title)};" for s in script.schemas]
        return notes, statements

    def column_comment(self, comment: str) -> str:
        return f" COMMENT {self.string(comment)}"

    def table_comment(self, comment: str) -> str:
        return f"\nCOMMENT = {self.string(comment)}"


class Redshift(Dialect):
    key = "redshift"
    title = "Redshift"
    three_part_names = False
    types = {
        "string": "VARCHAR(256)", "text": "VARCHAR(4096)", "json": "VARCHAR(4096)", "int": "INT",
        "bigint": "BIGINT", "date": "DATE", "timestamp": "TIMESTAMP", "bool": "BOOLEAN",
    }

    def string(self, value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    def days_ago(self, days: int) -> str:
        return "CURRENT_DATE" if days == 0 else f"CAST(DATEADD(day, {-days}, CURRENT_DATE) AS DATE)"

    def at(self, days_ago: int, minute: int) -> str:
        return f"DATEADD(minute, {minute}, DATEADD(day, {-days_ago}, CURRENT_DATE))"

    def add_days(self, expr: str, days: int | str) -> str:
        return f"CAST(DATEADD(day, {days}, {expr}) AS DATE)"

    def days_between(self, start: str, end: str) -> str:
        return f"DATEDIFF(day, CAST({start} AS DATE), CAST({end} AS DATE))"

    def month_start(self, expr: str) -> str:
        return f"CAST(DATE_TRUNC('month', {expr}) AS DATE)"

    def json_text(self, column: str, key: str) -> str:
        return f"JSON_EXTRACT_PATH_TEXT({column}, '{key}')"

    def setup(self, script: Script) -> tuple[list[str], list[str]]:
        notes = [
            f"Create the database once and connect to it before running this script:",
            f"  CREATE DATABASE {script.container};",
            "Redshift has no CREATE OR REPLACE TABLE, so tables are dropped and recreated.",
        ]
        statements = [f"CREATE SCHEMA IF NOT EXISTS {s.name};" for s in script.schemas]
        statements += [f"SET search_path TO {', '.join(s.name for s in script.schemas)};"]
        return notes, statements

    # No COMMENT ON: Redshift rejects it in some sessions ("Operation is not
    # supported through datashares"). Descriptions stay in the script comments.
    def create_table(self, name: str, table: Table) -> list[str]:
        columns = ",\n".join(f"  {c.name} {self.type(c.type)}" for c in table.columns)
        return [f"DROP TABLE IF EXISTS {name};", f"CREATE TABLE {name} (\n{columns}\n);"]

    def create_table_as(self, name: str, comment: str, select: str) -> list[str]:
        return [f"DROP TABLE IF EXISTS {name};", f"CREATE TABLE {name}\nAS\n{select.strip()};"]


class BigQuery(Dialect):
    key = "bigquery"
    title = "BigQuery"
    today = "CURRENT_DATE()"
    three_part_names = False
    types = {
        "string": "STRING", "text": "STRING", "json": "STRING", "int": "INT64", "bigint": "INT64",
        "date": "DATE", "timestamp": "TIMESTAMP", "bool": "BOOL",
    }

    def decimal_type(self, precision_scale: str) -> str:
        return f"NUMERIC({precision_scale})"

    def cast_type(self, logical: str) -> str:
        # BigQuery rejects parameterized types such as NUMERIC(18,2) in CAST.
        return "NUMERIC" if logical.startswith("decimal(") else self.type(logical)

    def money(self, expr: str) -> str:
        return f"ROUND(CAST({expr} AS NUMERIC), 2)"

    def decimal_literal(self, value: Decimal) -> str:
        return f"NUMERIC '{value}'"

    def days_ago(self, days: int) -> str:
        if days == 0:
            return "CURRENT_DATE()"
        if days > 0:
            return f"DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)"
        return f"DATE_ADD(CURRENT_DATE(), INTERVAL {-days} DAY)"

    def at(self, days_ago: int, minute: int) -> str:
        return f"TIMESTAMP_ADD(TIMESTAMP({self.days_ago(days_ago)}), INTERVAL {minute} MINUTE)"

    def add_days(self, expr: str, days: int | str) -> str:
        return f"DATE_ADD({expr}, INTERVAL {days} DAY)"

    def days_between(self, start: str, end: str) -> str:
        return f"DATE_DIFF(CAST({end} AS DATE), CAST({start} AS DATE), DAY)"

    def month_start(self, expr: str) -> str:
        return f"DATE_TRUNC(CAST({expr} AS DATE), MONTH)"

    def json_text(self, column: str, key: str) -> str:
        return f"JSON_VALUE({column}, '$.{key}')"

    def setup(self, script: Script) -> tuple[list[str], list[str]]:
        notes = [
            "Datasets are created in the project selected in the BigQuery console,",
            "in the project's default location.",
        ]
        statements = [
            f"CREATE SCHEMA IF NOT EXISTS {s.name}\nOPTIONS (description = {self.string(s.title)});"
            for s in script.schemas
        ]
        return notes, statements

    def column_comment(self, comment: str) -> str:
        return f" OPTIONS (description = {self.string(comment)})"

    def table_comment(self, comment: str) -> str:
        return f"\nOPTIONS (description = {self.string(comment)})"


class DuckDB(Dialect):
    """Used only by the tests, to run every script's SQL end to end."""

    key = "duckdb"
    title = "DuckDB"
    types = {
        "string": "VARCHAR", "text": "VARCHAR", "json": "VARCHAR", "int": "INTEGER", "bigint": "BIGINT",
        "date": "DATE", "timestamp": "TIMESTAMP", "bool": "BOOLEAN",
    }

    def string(self, value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    def days_ago(self, days: int) -> str:
        return f"CAST(CURRENT_DATE - INTERVAL ({days}) DAY AS DATE)"

    def at(self, days_ago: int, minute: int) -> str:
        return f"CAST(CURRENT_DATE AS TIMESTAMP) - INTERVAL ({days_ago}) DAY + INTERVAL ({minute}) MINUTE"

    def add_days(self, expr: str, days: int | str) -> str:
        return f"CAST({expr} + to_days(CAST({days} AS INTEGER)) AS DATE)"

    def days_between(self, start: str, end: str) -> str:
        return f"datediff('day', CAST({start} AS DATE), CAST({end} AS DATE))"

    def month_start(self, expr: str) -> str:
        return f"CAST(date_trunc('month', {expr}) AS DATE)"

    def json_text(self, column: str, key: str) -> str:
        return f"json_extract_string({column}, '$.{key}')"

    def initcap(self, expr: str) -> str:
        return f"(upper(left({expr}, 1)) || lower(substr({expr}, 2)))"

    def setup(self, script: Script) -> tuple[list[str], list[str]]:
        statements = []
        if script.container and self.three_part_names:
            statements.append(f"ATTACH IF NOT EXISTS ':memory:' AS {script.container};")
        statements += [
            f"CREATE SCHEMA IF NOT EXISTS {self.table(script.container, s.name, '')[:-1]};" for s in script.schemas
        ]
        return [], statements


DIALECTS: dict[str, Dialect] = {d.key: d for d in (Databricks(), Snowflake(), Redshift(), BigQuery(), DuckDB())}
