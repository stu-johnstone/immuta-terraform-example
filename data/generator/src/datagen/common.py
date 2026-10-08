"""Things shared by every company: the company profile and SQL snippets for
country, region and currency, so all gold tables answer region rules and
questions the same way."""

from __future__ import annotations

from dataclasses import dataclass

REGIONS = {
    "APAC": ("AU", "NZ", "SG", "JP", "IN", "MY", "ID", "HK"),
    "EMEA": ("GB", "IE", "DE", "FR", "NL", "AE", "ZA"),
    "AMER": ("US", "CA", "MX", "BR"),
}

# Fixed demo rates, so amounts in different currencies can be added up.
FX_TO_AUD = {"AUD": "1.00", "NZD": "0.92", "SGD": "1.13", "GBP": "1.95", "USD": "1.52", "EUR": "1.66"}

# Spellings that source systems use for countries, cleaned up in silver.
COUNTRY_ALIASES = {
    "AU": ("AUS", "AUSTRALIA"),
    "NZ": ("NZL", "NEW ZEALAND"),
    "SG": ("SGP", "SINGAPORE"),
    "GB": ("GBR", "UK", "UNITED KINGDOM"),
    "US": ("USA", "UNITED STATES"),
}


@dataclass(frozen=True)
class Company:
    key: str  # catalog/database/schema name, e.g. harbourstone
    name: str  # Harbourstone Financial Group
    folder: str  # data/<folder>
    industry: str
    employee_id_prefix: str  # HFG -> HFG00001
    email_domain: str  # work emails, e.g. harbourstone.example.com
    bsb_prefix: str  # first 3 digits of the company's fictional BSBs
    staff: int  # number of employees
    # (business unit, department, [(position title, pay grade)]) - the first
    # title in each department is its head.
    departments: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...]
    # Marketing: products campaigns promote, as (code, label), and the web
    # site's landing pages, as (path, product code).
    products: tuple[tuple[str, str], ...]
    landing_pages: tuple[tuple[str, str], ...]


def country_sql(column: str) -> str:
    """Cleans a raw country value to an ISO code."""
    cleaned = f"UPPER(TRIM({column}))"
    whens = " ".join(
        f"WHEN {cleaned} IN ({', '.join(repr(a) for a in (code, *aliases))}) THEN '{code}'"
        for code, aliases in COUNTRY_ALIASES.items()
    )
    return f"CASE {whens} ELSE {cleaned} END"


def region_sql(country: str) -> str:
    """APAC, EMEA or AMER for an ISO country code: the column region rules use."""
    whens = " ".join(
        f"WHEN {country} IN ({', '.join(repr(c) for c in codes)}) THEN '{region}'" for region, codes in REGIONS.items()
    )
    return f"CASE {whens} ELSE 'UNKNOWN' END"


def aud_sql(amount: str, currency: str, money) -> str:
    """Converts an amount to AUD at the fixed demo rates."""
    whens = " ".join(f"WHEN '{c}' THEN {rate}" for c, rate in FX_TO_AUD.items())
    return money(f"{amount} * CASE {currency} {whens} END")


def meta_columns():
    """Load metadata every bronze table carries."""
    from .model import Col

    return [Col("_source_system", "string"), Col("_batch_id", "string")]
