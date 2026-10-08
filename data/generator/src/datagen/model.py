"""What a generated script is made of.

A Script is one .sql file: a company's data for one platform. It holds
Schemas (one per business, or the HR/marketing dataset), each with bronze
tables that carry rows, and silver and gold tables derived from them with
SQL.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class DaysAgo:
    """A date relative to the day the script runs, so that questions such as
    "what were deposits today" always have data. Negative means future."""

    days: int


@dataclass(frozen=True)
class At:
    """A timestamp: `minute` minutes after midnight, `days_ago` days before
    the day the script runs."""

    days_ago: int
    minute: int


Value = None | bool | int | Decimal | str | date | DaysAgo | At


@dataclass(frozen=True)
class Col:
    """A column. `type` is a logical type: string, text, int, bigint,
    decimal(p,s), date, timestamp, bool or json; dialects map it to the
    platform's type. `comment` is shown in the script and on the column."""

    name: str
    type: str
    comment: str = ""


@dataclass
class Table:
    """A bronze table: created and loaded with rows."""

    name: str
    comment: str
    columns: list[Col]
    rows: list[tuple[Value, ...]]

    def __post_init__(self) -> None:
        width = len(self.columns)
        for row in self.rows:
            if len(row) != width:
                raise ValueError(f"{self.name}: row has {len(row)} values, expected {width}: {row}")


class Sql:
    """Helpers available to derived-table SQL: the dialect `d` and `ref`,
    which qualifies a table name and checks it was created earlier."""

    def __init__(self, dialect, ref: Callable[[str], str]) -> None:
        self.d = dialect
        self.ref = ref


@dataclass
class Derived:
    """A silver or gold table, created from earlier tables with a SELECT.
    `select` is given a Sql helper and returns the SELECT statement."""

    name: str
    comment: str
    select: Callable[[Sql], str]


@dataclass
class Schema:
    """A schema (Databricks, Snowflake, Redshift) or dataset (BigQuery)."""

    name: str
    title: str
    description: str
    bronze: list[Table]
    silver: list[Derived] = field(default_factory=list)
    gold: list[Derived] = field(default_factory=list)


@dataclass
class Script:
    """One generated .sql file. `container` is the catalog (Databricks) or
    database (Snowflake, Redshift); BigQuery uses the console's project."""

    path: str
    title: str
    description: str
    platform: str
    container: str | None
    schemas: list[Schema]
