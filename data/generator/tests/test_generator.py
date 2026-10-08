"""Checks the generated SQL: it runs end to end (in DuckDB), parses for each
platform, stays the same between runs and matches the committed files."""

from __future__ import annotations

import re

import duckdb
import pytest
import sqlglot

from datagen.cli import generate
from datagen.companies import scripts
from datagen.dialects import DIALECTS
from datagen.model import Table
from datagen.render import statements

SCRIPTS = scripts()
IDS = [s.path for s in SCRIPTS]
# BigQuery rejects scripts over 1,024K characters.
MAX_CHARS = {"bigquery": 1_000_000}


@pytest.mark.parametrize("script", SCRIPTS, ids=IDS)
def test_runs_end_to_end(script):
    """Every statement runs, so silver and gold only use columns and tables
    that exist, and every table ends up with rows."""
    db = duckdb.connect()
    dialect = DIALECTS["duckdb"]
    for statement in statements(script, dialect):
        db.execute(statement)
    for schema in script.schemas:
        for table in [*schema.bronze, *schema.silver, *schema.gold]:
            name = dialect.table(script.container, schema.name, table.name)
            count = db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            assert count > 0, f"{name} is empty"


@pytest.mark.parametrize("script", SCRIPTS, ids=IDS)
def test_parses_for_platform(script):
    dialect = DIALECTS[script.platform]
    for statement in statements(script, dialect):
        if statement.startswith("COMMENT ON"):
            continue  # not modelled by sqlglot
        sqlglot.parse_one(statement, read=script.platform)


@pytest.mark.parametrize("script", [s for s in SCRIPTS if s.platform == "databricks"], ids=lambda s: s.path)
def test_databricks_uses_current_catalog(script):
    """Each person has their own catalog in a shared workspace, so scripts
    never name a catalog, and stop if a shared or built-in one is selected."""
    sql = statements(script, DIALECTS["databricks"])
    assert sql[0].startswith("SELECT assert_true(current_catalog() NOT IN (")
    assert "'main'" in sql[0]
    for statement in sql:
        assert not statement.startswith("CREATE CATALOG")
        for schema in script.schemas:
            assert f"{script.container}.{schema.name}" not in statement


@pytest.mark.parametrize("script", [s for s in SCRIPTS if s.platform == "bigquery"], ids=lambda s: s.path)
def test_bigquery_casts_are_not_parameterized(script):
    """BigQuery rejects types such as NUMERIC(18,2) in CAST; sqlglot accepts them."""
    for statement in statements(script, DIALECTS["bigquery"]):
        assert not re.search(r"\bAS\s+(BIG)?NUMERIC\s*\(", statement), statement[:200]


@pytest.mark.parametrize("script", SCRIPTS, ids=IDS)
def test_data_is_safe_to_quote(script):
    """Backslashes are escaped differently on each platform; keep them out."""
    for schema in script.schemas:
        for table in schema.bronze:
            for row in table.rows:
                for value in row:
                    assert not (isinstance(value, str) and "\\" in value), f"{table.name}: {value}"


@pytest.mark.parametrize("script", SCRIPTS, ids=IDS)
def test_row_counts_and_size(script):
    for schema in script.schemas:
        for table in schema.bronze:
            assert isinstance(table, Table)
            assert 10 <= len(table.rows) <= 1100, f"{table.name} has {len(table.rows)} rows"
    text = generate()[next(p for p in generate() if str(p).endswith(script.path))]
    assert len(text) < MAX_CHARS.get(script.platform, 2_000_000)


def test_deterministic():
    assert generate() == generate()


def test_committed_files_are_up_to_date():
    for path, text in generate().items():
        assert path.exists() and path.read_text() == text, f"{path} is out of date: run make data"


def test_no_reserved_words_as_columns():
    reserved = {"date", "timestamp", "user", "limit", "order", "group", "year", "month", "level", "comment", "type", "role", "rows"}
    for script in SCRIPTS:
        for schema in script.schemas:
            for table in schema.bronze:
                for column in table.columns:
                    assert column.name not in reserved, f"{table.name}.{column.name}"
                    assert re.fullmatch(r"_?[a-z][a-z0-9_]*", column.name)
