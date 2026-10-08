"""Commercial banking: business customers, their directors and owners,
lending facilities, collateral, covenants, repayments and credit reviews.

Each business has a risk grade from 1 (strong) to 10 (default). Higher
grades make arrears, covenant breaches and worrying analyst commentary more
likely, so the risk profile tells a consistent story."""

from __future__ import annotations

from decimal import Decimal

from ... import fake, hr
from ...common import aud_sql, meta_columns, region_sql
from ...model import Col, DaysAgo, Derived, Schema, Sql, Table
from . import COMPANY

INDUSTRIES = {
    "Construction": ("Builders", "Constructions", "Civil"), "Agriculture": ("Farms", "Pastoral", "Orchards"),
    "Retail Trade": ("Stores", "Outfitters", "Traders"), "Manufacturing": ("Fabrication", "Engineering", "Plastics"),
    "Hospitality": ("Hotels", "Dining Group", "Hospitality"), "Transport and Logistics": ("Freight", "Logistics", "Haulage"),
    "Professional Services": ("Consulting", "Advisory", "Partners"), "Health Care": ("Medical", "Dental Group", "Health"),
    "Property Development": ("Developments", "Property Group", "Estates"), "Mining Services": ("Drilling", "Mining Services", "Resources"),
}
NAME_WORDS = ("Southern Cross", "Bluegum", "Ironbark", "Harbour View", "Red Gum", "Coastal", "Summit", "Wattle", "Kestrel",
              "Granite", "Silver Creek", "Banksia", "Northern Star", "Pinnacle", "Riverbend", "Tasman", "Brolga", "Eucalypt")
SUFFIX = {"AU": "Pty Ltd", "NZ": "Limited", "SG": "Pte Ltd", "GB": "Ltd", "US": "LLC"}
COUNTRIES = {"AU": 78, "NZ": 8, "SG": 6, "GB": 5, "US": 3}
GRADES = {1: 6, 2: 10, 3: 18, 4: 21, 5: 16, 6: 12, 7: 7, 8: 5, 9: 3, 10: 2}
PD_PCT = {1: "0.03", 2: "0.10", 3: "0.25", 4: "0.50", 5: "1.00", 6: "2.00", 7: "5.00", 8: "10.00", 9: "20.00", 10: "100.00"}
FACILITY_TYPES = {"TERM_LOAN": 35, "OVERDRAFT": 25, "EQUIPMENT_FINANCE": 15, "COMMERCIAL_PROPERTY": 15, "TRADE_FINANCE": 10}
AMORTISING = ("TERM_LOAN", "EQUIPMENT_FINANCE", "COMMERCIAL_PROPERTY")
COVENANTS = {"DSCR": ("MIN", "1.25"), "INTEREST_COVER": ("MIN", "2.00"), "LVR": ("MAX", "70.00"), "LEVERAGE": ("MAX", "3.00")}
COMMENTARY = {
    "LOW": "{name} continues to trade strongly in {industry}. Revenue of about {revenue} million is up on last year and debt service cover is comfortable at {dscr}x. No concerns; grade maintained.",
    "MEDIUM": "{name} is trading in line with budget, but margins in {industry} are under pressure from rising costs. Debt service cover of {dscr}x is adequate. Monitor quarterly management accounts.",
    "HIGH": "{name} reported a second consecutive quarterly loss. The largest customer is about 40 percent of revenue. Debt service cover has fallen to {dscr}x, close to covenant. Updated cash flow forecast requested from director {director}.",
    "WATCHLIST": "{name} breached its debt service covenant and is {arrears} days in arrears. Director {director} advised a major contract was lost. Referred to the business recovery team; updated property valuation ordered.",
}
REPAYMENT_DAYS_AGO = (5, 35, 65, 95, 125, 155)


def band(grade: int) -> str:
    return "LOW" if grade <= 4 else "MEDIUM" if grade <= 6 else "HIGH" if grade <= 8 else "WATCHLIST"


def bronze() -> list[Table]:
    m = meta_columns()
    meta = ("LOANIQ", "loaniq-0412")
    r = fake.rng("harbourstone", "commercial", "businesses")
    bankers = [p for p in hr.staff_in(COMPANY, "COMMERCIAL_BANKING") if "Relationship" in p["title"] or p["is_head"]]
    analysts = [p for p in hr.staff_in(COMPANY, "COMMERCIAL_BANKING") if "Credit" in p["title"]]

    rm_rows = [(p["employee_id"], f"{p['first_name']} {p['last_name']}", p["work_email"], p["title"],
                f"Business Banking {p['country']}", *meta) for p in bankers]

    businesses = []
    used_names = set()
    for i in range(100):
        country = fake.weighted(r, COUNTRIES)
        industry = r.choice(list(INDUSTRIES))
        name = f"{r.choice(NAME_WORDS)} {r.choice(INDUSTRIES[industry])}"
        while name in used_names:
            name = f"{r.choice(NAME_WORDS)} {r.choice(INDUSTRIES[industry])}"
        used_names.add(name)
        registration = {
            "AU": (fake.abn(r), "ABN"), "NZ": (f"94290{fake.digits(r, 8)}", "NZBN"), "SG": (f"20{fake.digits(r, 7)}{r.choice('KMNRZ')}", "UEN"),
            "GB": (fake.digits(r, 8), "COMPANY_NUMBER"), "US": (f"{fake.digits(r, 2)}-{fake.digits(r, 7)}", "EIN"),
        }[country]
        businesses.append({
            "id": f"B{30001 + i}", "legal": f"{name} {SUFFIX[country]}", "trading": name, "country": country,
            "industry": industry, "registration": registration, "revenue": Decimal(r.randint(5, 2500)) * 100000,
            "employees": r.randint(4, 900), "rm": r.choice(bankers)["employee_id"], "grade": int(fake.weighted(r, {str(k): v for k, v in GRADES.items()})),
            "since": r.randint(90, 365 * 15), "address": fake.address(r, country),
        })
    business_rows = [
        (b["id"], b["legal"], b["trading"], b["registration"][0], b["registration"][1], b["industry"], b["revenue"], b["employees"],
         b["address"]["address_line"], b["address"]["suburb"], b["address"]["state"], b["country"], b["rm"], DaysAgo(b["since"]), *meta)
        for b in businesses
    ]

    r = fake.rng("harbourstone", "commercial", "contacts")
    contact_rows, directors = [], {}
    for b in businesses:
        for role in ("DIRECTOR", r.choice(("BENEFICIAL_OWNER", "CFO", "DIRECTOR"))):
            first, last = fake.name(r)
            residence = b["country"] if fake.chance(r, 0.9) else fake.weighted(r, COUNTRIES)
            directors.setdefault(b["id"], f"{first} {last}")
            contact_rows.append((f"BC{len(contact_rows) + 1:06d}", b["id"], f"{first} {last}", role,
                                 Decimal(r.randint(10, 100)) if role in ("BENEFICIAL_OWNER", "DIRECTOR") and fake.chance(r, 0.6) else None,
                                 fake.birth_date(r, 28, 75), fake.email(r, first, last), fake.phone(r, residence), residence,
                                 fake.chance(r, 0.02), *meta))

    r = fake.rng("harbourstone", "commercial", "facilities")
    facilities = []
    for b in businesses:
        for _ in range(r.choice((1, 1, 2, 2, 3))):
            kind = fake.weighted(r, FACILITY_TYPES)
            limit = (b["revenue"] * fake.rate(r, 0.05, 0.4)).quantize(Decimal("1000"))
            utilisation = fake.rate(r, 0.2, 0.7) if b["grade"] <= 6 else fake.rate(r, 0.85, 1.05)
            if kind in AMORTISING:
                utilisation = fake.rate(r, 0.5, 0.95)
            start = r.randint(60, 2500)
            facilities.append({
                "id": f"F{50001 + len(facilities)}", "business": b, "type": kind, "limit": limit,
                "drawn": (limit * utilisation).quantize(Decimal("0.01")), "rate": fake.rate(r, 6.2, 11.5),
                "start": start, "maturity": start - r.choice((365, 1095, 1825, 3650)), "currency": fake.CURRENCIES[b["country"]],
            })
    facility_rows = [
        (f["id"], f["business"]["id"], f["type"], f["currency"], f["limit"], f["drawn"], f["rate"], DaysAgo(f["start"]),
         DaysAgo(f["maturity"]), "ACTIVE" if f["business"]["grade"] < 9 else "IMPAIRED", *meta)
        for f in facilities
    ]

    r = fake.rng("harbourstone", "commercial", "collateral")
    collateral_rows = []
    for f in facilities:
        if not fake.chance(r, 0.8):
            continue
        kind = {"COMMERCIAL_PROPERTY": "PROPERTY", "EQUIPMENT_FINANCE": "EQUIPMENT"}.get(f["type"]) or r.choice(("PROPERTY", "RECEIVABLES", "GUARANTEE", "CASH"))
        a = fake.address(r, f["business"]["country"])
        description = {
            "PROPERTY": f"First mortgage over {r.choice(('warehouse', 'office', 'retail premises', 'workshop'))} at {a['address_line']}, {a['suburb']}",
            "EQUIPMENT": f"{r.choice(('Excavator', 'Delivery trucks', 'CNC machines', 'Commercial kitchen fit-out', 'Refrigerated trailers'))}, serials on file",
            "RECEIVABLES": "General security over trade receivables",
            "GUARANTEE": f"Personal guarantee from director {directors[f['business']['id']]}",
            "CASH": "Cash cover held in term deposit",
        }[kind]
        value = (f["limit"] * (fake.rate(r, 0.9, 1.8) if f["business"]["grade"] <= 6 else fake.rate(r, 0.5, 1.1))).quantize(Decimal("1000"))
        collateral_rows.append((f"COL{len(collateral_rows) + 1:05d}", f["id"], kind, description, value,
                                DaysAgo(r.randint(20, 900)), *meta))

    r = fake.rng("harbourstone", "commercial", "covenants")
    covenant_rows = []
    for f in facilities:
        if f["type"] not in ("TERM_LOAN", "COMMERCIAL_PROPERTY"):
            continue
        for covenant in r.sample(list(COVENANTS), r.choice((1, 2))):
            direction, threshold = COVENANTS[covenant]
            threshold = Decimal(threshold)
            for test_days_ago in (30, 120):
                breach = fake.chance(r, {"LOW": 0.02, "MEDIUM": 0.1, "HIGH": 0.4, "WATCHLIST": 0.8}[band(f["business"]["grade"])])
                if direction == "MIN":
                    actual = threshold * (fake.rate(r, 0.6, 0.97) if breach else fake.rate(r, 1.05, 2.4))
                else:
                    actual = threshold * (fake.rate(r, 1.03, 1.4) if breach else fake.rate(r, 0.4, 0.95))
                covenant_rows.append((f"COV{len(covenant_rows) + 1:05d}", f["id"], covenant, direction, threshold,
                                      actual.quantize(Decimal("0.01")), DaysAgo(test_days_ago), *meta))

    r = fake.rng("harbourstone", "commercial", "repayments")
    repayment_rows = []
    for f in facilities:
        if f["type"] not in AMORTISING:
            continue
        due = (f["limit"] / 60).quantize(Decimal("0.01"))
        late_chance = {"LOW": 0.03, "MEDIUM": 0.12, "HIGH": 0.35, "WATCHLIST": 0.7}[band(f["business"]["grade"])]
        for days_ago in REPAYMENT_DAYS_AGO:
            if days_ago > f["start"]:
                continue
            if not fake.chance(r, late_chance):
                paid, amount = DaysAgo(days_ago - r.randint(-2, 0)), due
            elif fake.chance(r, 0.5) and days_ago > 20:
                paid, amount = DaysAgo(days_ago - r.randint(5, 20)), due
            else:
                paid, amount = None, Decimal("0.00")
            repayment_rows.append((f"RP{len(repayment_rows) + 1:06d}", f["id"], DaysAgo(days_ago), due, paid, amount, *meta))

    r = fake.rng("harbourstone", "commercial", "reviews")
    review_rows = []
    for b in businesses:
        previous_grade = max(1, min(10, b["grade"] + r.choice((-1, 0, 0, 1)) * (-1 if b["grade"] >= 7 else 1)))
        for grade, days_ago in ((previous_grade, r.randint(200, 420)), (b["grade"], r.randint(5, 120))):
            dscr = {"LOW": fake.rate(r, 1.8, 3.2), "MEDIUM": fake.rate(r, 1.3, 1.8), "HIGH": fake.rate(r, 1.1, 1.3), "WATCHLIST": fake.rate(r, 0.6, 1.0)}[band(grade)]
            text = COMMENTARY[band(grade)].format(name=b["trading"], industry=b["industry"].lower(), revenue=b["revenue"] // 1000000 or 1,
                                                  dscr=dscr, director=directors[b["id"]], arrears=r.choice((35, 64, 95)))
            review_rows.append((f"CR{len(review_rows) + 1:05d}", b["id"], DaysAgo(days_ago), grade, Decimal(PD_PCT[grade]),
                                r.choice(analysts)["employee_id"], text, *meta))

    return [
        Table("bronze_relationship_managers", "Relationship managers, from the commercial lending system (LoanIQ).", [
            Col("rm_employee_id", "string", "Matches employee_id in the HR data"), Col("rm_name", "string", "Person name"),
            Col("rm_email", "string"), Col("position_title", "string"), Col("team", "string"), *m], rm_rows),
        Table("bronze_business_customers", "Business customers from the commercial lending system.", [
            Col("business_id", "string"), Col("legal_name", "string"), Col("trading_name", "string"),
            Col("registration_number", "string", "Business identifier: ABN, NZBN, UEN, company number or EIN"),
            Col("registration_type", "string"), Col("industry", "string"), Col("annual_revenue", "decimal(16,2)", "Commercially sensitive"),
            Col("employee_count", "int"), Col("address_line", "string"), Col("suburb", "string"), Col("state", "string"),
            Col("country", "string"), Col("rm_employee_id", "string"), Col("customer_since", "date"), *m], business_rows),
        Table("bronze_business_contacts", "Directors, beneficial owners and finance contacts of business customers (KYC).", [
            Col("contact_id", "string"), Col("business_id", "string"), Col("full_name", "string", "Person name"),
            Col("contact_role", "string"), Col("ownership_pct", "decimal(5,1)"), Col("date_of_birth", "date", "PII: date of birth"),
            Col("email", "string", "PII: email"), Col("phone", "string", "PII: phone number"), Col("residential_country", "string"),
            Col("is_politically_exposed", "bool", "Sensitive: politically exposed person (PEP)"), *m], contact_rows),
        Table("bronze_facilities", "Lending facilities: term loans, overdrafts, equipment, property and trade finance.", [
            Col("facility_id", "string"), Col("business_id", "string"), Col("facility_type", "string"), Col("currency", "string"),
            Col("limit_amount", "decimal(16,2)"), Col("drawn_amount", "decimal(16,2)"), Col("interest_rate", "decimal(5,2)"),
            Col("start_date", "date"), Col("maturity_date", "date"), Col("facility_status", "string"), *m], facility_rows),
        Table("bronze_collateral", "Security held against facilities, with the latest valuation.", [
            Col("collateral_id", "string"), Col("facility_id", "string"), Col("collateral_type", "string"),
            Col("description", "string", "Free text: may include addresses and guarantor names"),
            Col("valuation_amount", "decimal(16,2)"), Col("valuation_date", "date"), *m], collateral_rows),
        Table("bronze_covenants", "Financial covenant tests for the last two quarters. MIN covenants breach below the threshold, MAX above.", [
            Col("covenant_id", "string"), Col("facility_id", "string"), Col("covenant_type", "string"),
            Col("direction", "string"), Col("threshold", "decimal(8,2)"), Col("actual_value", "decimal(8,2)"),
            Col("test_date", "date"), *m], covenant_rows),
        Table("bronze_repayments", "Scheduled repayments for the last six months; paid_date is empty when missed.", [
            Col("repayment_id", "string"), Col("facility_id", "string"), Col("due_date", "date"), Col("amount_due", "decimal(14,2)"),
            Col("paid_date", "date"), Col("amount_paid", "decimal(14,2)"), *m], repayment_rows),
        Table("bronze_credit_reviews", "Annual credit reviews: risk grade, probability of default and the analyst's commentary.", [
            Col("review_id", "string"), Col("business_id", "string"), Col("review_date", "date"),
            Col("risk_grade", "int", "1 (strong) to 10 (default)"), Col("probability_of_default_pct", "decimal(6,2)"),
            Col("analyst_employee_id", "string"), Col("commentary", "text", "Free text: credit assessment, names directors"), *m], review_rows),
    ]


def silver() -> list[Derived]:
    def businesses_sql(s: Sql) -> str:
        return f"""
SELECT
  b.business_id,
  TRIM(b.legal_name) AS legal_name,
  b.trading_name,
  REGEXP_REPLACE(b.registration_number, '[^0-9A-Za-z]', '') AS registration_number,
  b.registration_type,
  b.industry,
  b.annual_revenue,
  b.employee_count,
  b.suburb,
  b.state,
  b.country,
  {region_sql('b.country')} AS region,
  b.rm_employee_id,
  rm.rm_name,
  b.customer_since
FROM {s.ref('bronze_business_customers')} b
LEFT JOIN {s.ref('bronze_relationship_managers')} rm ON rm.rm_employee_id = b.rm_employee_id"""

    def contacts_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  c.contact_id,
  c.business_id,
  c.full_name,
  c.contact_role,
  c.ownership_pct,
  c.date_of_birth,
  {d.age('c.date_of_birth')} AS age,
  LOWER(c.email) AS email,
  c.phone,
  c.residential_country,
  c.is_politically_exposed,
  b.region
FROM {s.ref('bronze_business_contacts')} c
JOIN {s.ref('silver_business_customers')} b ON b.business_id = c.business_id"""

    def facilities_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  f.facility_id,
  f.business_id,
  f.facility_type,
  f.currency,
  f.limit_amount,
  f.drawn_amount,
  {aud_sql('f.limit_amount', 'f.currency', d.money)} AS limit_aud,
  {aud_sql('f.drawn_amount', 'f.currency', d.money)} AS drawn_aud,
  ROUND(f.drawn_amount * 100 / NULLIF(f.limit_amount, 0), 1) AS utilisation_pct,
  f.interest_rate,
  f.start_date,
  f.maturity_date,
  {d.days_between(d.today, 'f.maturity_date')} AS days_to_maturity,
  f.facility_status,
  b.industry,
  b.country,
  b.region
FROM {s.ref('bronze_facilities')} f
JOIN {s.ref('silver_business_customers')} b ON b.business_id = f.business_id"""

    def collateral_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  c.collateral_id,
  c.facility_id,
  f.business_id,
  c.collateral_type,
  c.description,
  c.valuation_amount,
  {aud_sql('c.valuation_amount', 'f.currency', d.money)} AS valuation_aud,
  c.valuation_date,
  f.region
FROM {s.ref('bronze_collateral')} c
JOIN {s.ref('silver_facilities')} f ON f.facility_id = c.facility_id"""

    def covenants_sql(s: Sql) -> str:
        return f"""
SELECT
  c.covenant_id,
  c.facility_id,
  f.business_id,
  c.covenant_type,
  c.direction,
  c.threshold,
  c.actual_value,
  c.test_date,
  CASE WHEN c.direction = 'MIN' AND c.actual_value < c.threshold THEN TRUE
       WHEN c.direction = 'MAX' AND c.actual_value > c.threshold THEN TRUE
       ELSE FALSE END AS is_breached,
  f.region
FROM {s.ref('bronze_covenants')} c
JOIN {s.ref('silver_facilities')} f ON f.facility_id = c.facility_id"""

    def repayments_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  p.repayment_id,
  p.facility_id,
  f.business_id,
  f.facility_type,
  p.due_date,
  {d.month_start('p.due_date')} AS due_month,
  p.amount_due,
  p.paid_date,
  p.amount_paid,
  CASE WHEN p.paid_date IS NULL THEN TRUE ELSE FALSE END AS is_missed,
  CASE WHEN p.paid_date IS NULL THEN {d.days_between('p.due_date', d.today)}
       WHEN p.paid_date > p.due_date THEN {d.days_between('p.due_date', 'p.paid_date')}
       ELSE 0 END AS days_late,
  {aud_sql('p.amount_due - p.amount_paid', 'f.currency', d.money)} AS shortfall_aud,
  f.region
FROM {s.ref('bronze_repayments')} p
JOIN {s.ref('silver_facilities')} f ON f.facility_id = p.facility_id"""

    def reviews_sql(s: Sql) -> str:
        return f"""
WITH ranked AS (
  SELECT r.*, ROW_NUMBER() OVER (PARTITION BY r.business_id ORDER BY r.review_date DESC) AS rn
  FROM {s.ref('bronze_credit_reviews')} r
)
SELECT
  r.review_id,
  r.business_id,
  r.review_date,
  r.risk_grade,
  CASE WHEN r.risk_grade <= 4 THEN 'LOW' WHEN r.risk_grade <= 6 THEN 'MEDIUM' WHEN r.risk_grade <= 8 THEN 'HIGH' ELSE 'WATCHLIST' END AS risk_band,
  r.probability_of_default_pct,
  r.analyst_employee_id,
  r.commentary,
  CASE WHEN r.rn = 1 THEN TRUE ELSE FALSE END AS is_latest,
  b.region
FROM ranked r
JOIN {s.ref('silver_business_customers')} b ON b.business_id = r.business_id"""

    return [
        Derived("silver_business_customers", "Business customers with cleaned registration numbers, relationship manager and region.", businesses_sql),
        Derived("silver_business_contacts", "Directors and owners with age and the business's region.", contacts_sql),
        Derived("silver_facilities", "Facilities with AUD amounts, utilisation, days to maturity, industry and region.", facilities_sql),
        Derived("silver_collateral", "Collateral with AUD valuation and region.", collateral_sql),
        Derived("silver_covenants", "Covenant tests with a breach flag.", covenants_sql),
        Derived("silver_repayments", "Repayments with missed flag, days late and AUD shortfall.", repayments_sql),
        Derived("silver_credit_reviews", "Credit reviews with risk band; is_latest marks each business's current review.", reviews_sql),
    ]


def gold() -> list[Derived]:
    def risk_profile_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH exposure AS (
  SELECT business_id, COUNT(*) AS facilities, SUM(limit_aud) AS total_limit_aud, SUM(drawn_aud) AS total_drawn_aud
  FROM {s.ref('silver_facilities')}
  GROUP BY business_id
),
security AS (
  SELECT business_id, SUM(valuation_aud) AS collateral_aud FROM {s.ref('silver_collateral')} GROUP BY business_id
),
breaches AS (
  SELECT business_id, SUM(CASE WHEN is_breached THEN 1 ELSE 0 END) AS covenant_breaches
  FROM {s.ref('silver_covenants')}
  GROUP BY business_id
),
arrears AS (
  SELECT business_id, SUM(CASE WHEN is_missed THEN 1 ELSE 0 END) AS missed_repayments, MAX(days_late) AS max_days_late,
         SUM(shortfall_aud) AS arrears_aud
  FROM {s.ref('silver_repayments')}
  GROUP BY business_id
)
SELECT
  b.business_id,
  b.legal_name,
  b.industry,
  b.country,
  b.region,
  b.rm_name AS relationship_manager,
  e.facilities,
  e.total_limit_aud,
  e.total_drawn_aud,
  {d.pct('e.total_drawn_aud', 'e.total_limit_aud')} AS utilisation_pct,
  COALESCE(sc.collateral_aud, 0) AS collateral_aud,
  ROUND(COALESCE(sc.collateral_aud, 0) / NULLIF(e.total_drawn_aud, 0), 2) AS collateral_cover_ratio,
  r.risk_grade,
  r.risk_band,
  r.probability_of_default_pct,
  COALESCE(br.covenant_breaches, 0) AS covenant_breaches_6_months,
  COALESCE(a.missed_repayments, 0) AS missed_repayments_6_months,
  COALESCE(a.max_days_late, 0) AS max_days_late,
  COALESCE(a.arrears_aud, 0) AS arrears_aud,
  r.review_date AS latest_review_date,
  r.commentary AS latest_analyst_commentary
FROM {s.ref('silver_business_customers')} b
JOIN exposure e ON e.business_id = b.business_id
LEFT JOIN security sc ON sc.business_id = b.business_id
LEFT JOIN breaches br ON br.business_id = b.business_id
LEFT JOIN arrears a ON a.business_id = b.business_id
LEFT JOIN {s.ref('silver_credit_reviews')} r ON r.business_id = b.business_id AND r.is_latest"""

    def industry_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  industry,
  region,
  COUNT(*) AS borrowers,
  SUM(total_limit_aud) AS total_limit_aud,
  SUM(total_drawn_aud) AS total_drawn_aud,
  {d.pct('SUM(total_drawn_aud)', 'SUM(total_limit_aud)')} AS utilisation_pct,
  ROUND(AVG(CAST(risk_grade AS {d.type('decimal(4,2)')})), 1) AS avg_risk_grade,
  SUM(CASE WHEN risk_band IN ('HIGH', 'WATCHLIST') THEN 1 ELSE 0 END) AS high_risk_borrowers,
  SUM(CASE WHEN risk_band IN ('HIGH', 'WATCHLIST') THEN total_drawn_aud ELSE 0 END) AS high_risk_drawn_aud,
  SUM(covenant_breaches_6_months) AS covenant_breaches_6_months,
  SUM(arrears_aud) AS arrears_aud
FROM {s.ref('gold_risk_profile')}
GROUP BY 1, 2"""

    def arrears_sql(s: Sql) -> str:
        return f"""
SELECT
  due_month,
  facility_type,
  region,
  COUNT(*) AS repayments_due,
  SUM(amount_due) AS amount_due,
  SUM(amount_paid) AS amount_paid,
  SUM(CASE WHEN is_missed THEN 1 ELSE 0 END) AS missed_repayments,
  SUM(CASE WHEN days_late > 0 THEN 1 ELSE 0 END) AS late_repayments,
  SUM(shortfall_aud) AS shortfall_aud
FROM {s.ref('silver_repayments')}
GROUP BY 1, 2, 3"""

    return [
        Derived("gold_risk_profile", "One row per business borrower: exposure, utilisation, collateral cover, risk grade, covenant breaches, arrears and the latest analyst commentary.", risk_profile_sql),
        Derived("gold_portfolio_by_industry", "Commercial lending book by industry and region: exposure, average risk grade, high-risk borrowers, breaches and arrears.", industry_sql),
        Derived("gold_arrears_monthly", "Repayments due, paid, late and missed per month, facility type and region.", arrears_sql),
    ]


def schema() -> Schema:
    return Schema(
        "commercial_banking",
        "Harbourstone Commercial Banking",
        "Business lending: business customers, directors and beneficial owners, facilities, collateral, "
        "covenants, repayments and credit reviews. Source: the commercial lending system (LoanIQ).",
        bronze(), silver(), gold(),
    )
