"""HR data for a company: one schema per company in the Redshift hr database.

The same structure for every company, so one policy or framework (such as
the HR framework tagging employee names) can be shown across businesses.
employees() is also used by the company's own data, so staff IDs in, for
example, CRM notes match the HR records.
"""

from __future__ import annotations

from decimal import Decimal

from . import fake
from .common import Company, aud_sql, country_sql, meta_columns, region_sql
from .model import Col, DaysAgo, Derived, Schema, Script, Sql, Table

COUNTRY_WEIGHTS = {"AU": 82, "NZ": 7, "SG": 6, "GB": 5}
WORK_LOCATIONS = {
    "AU": ("Sydney", "Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"),
    "NZ": ("Auckland",),
    "SG": ("Singapore",),
    "GB": ("London",),
}
SALARY_BANDS = {
    "G2": (58_000, 72_000), "G3": (68_000, 88_000), "G4": (85_000, 110_000), "G5": (105_000, 135_000),
    "G6": (130_000, 165_000), "G7": (160_000, 210_000), "G8": (200_000, 280_000), "G9": (280_000, 420_000),
}
TERMINATION_REASONS = ("Resigned", "Resigned", "Resigned", "Redundancy", "Retirement", "End of contract", "Dismissed - misconduct")
LEAVE_REASONS = {
    "ANNUAL": ("Family holiday to Bali", "Wedding in Melbourne", "School holidays with the kids", "Moving house",
               "Trip to Japan", "Long weekend away", "Visiting family overseas"),
    "SICK": ("Flu, medical certificate provided", "Migraine", "Gastro", "Day surgery for knee arthroscopy",
             "Back injury, physio appointments", "Mental health day", "COVID-19 positive test",
             "Recovering from wisdom teeth removal"),
    "CARERS": ("Caring for child with chickenpox", "Taking parent to oncology appointment",
               "Partner recovering from surgery"),
    "PARENTAL": ("Birth of second child", "Primary carer leave", "Adoption of a child"),
    "LONG_SERVICE": ("Long service leave, travelling Europe", "Long service leave, renovating home"),
}
REVIEW_TEXT = {
    5: "{first} had an outstanding year, exceeding every objective. Led the {dept} uplift and mentored two new starters. Ready for promotion.",
    4: "{first} consistently delivered above expectations in {dept}. Strong stakeholder feedback. Development focus: delegating more.",
    3: "{first} met expectations in {dept}. Reliable delivery; would benefit from taking on a cross-team project next year.",
    2: "{first} partially met expectations. Deadlines in {dept} were missed in Q2 and Q3. A performance improvement plan has been agreed.",
    1: "{first} did not meet expectations. Ongoing attendance issues following extended sick leave; HR and the manager to agree a return to work plan.",
}
RELATIONSHIPS = ("Spouse", "Partner", "Mother", "Father", "Sibling", "Friend")
PAY_PERIOD_DAYS_AGO = (3, 17, 31, 45)

_employees: dict[str, list[dict]] = {}


def departments(company: Company) -> list[dict]:
    return [
        {"department_id": f"D{i:02d}", "business_unit": bu, "department_name": dept, "titles": titles,
         "cost_centre": f"CC{1000 + i * 10}"}
        for i, (bu, dept, titles) in enumerate(company.departments, start=1)
    ]


def employees(company: Company) -> list[dict]:
    """The company's employees. The first is the CEO; the next one per
    department are the department heads."""
    if company.key in _employees:
        return _employees[company.key]
    r = fake.rng(company.key, "hr", "employees")
    depts = departments(company)
    people: list[dict] = []
    used_emails: set[str] = set()
    for i in range(company.staff):
        is_head = i < len(depts)
        dept = depts[i] if is_head else r.choices(depts, weights=[len(d["titles"]) for d in depts])[0]
        title, grade = dept["titles"][0] if is_head or len(dept["titles"]) == 1 else r.choice(dept["titles"][1:])
        country = "AU" if is_head else fake.weighted(r, COUNTRY_WEIGHTS)
        first, last = fake.name(r)
        work_email = f"{first}.{last}".lower()
        while f"{work_email}@{company.email_domain}" in used_emails:
            work_email += str(r.randint(1, 9))
        work_email = f"{work_email}@{company.email_domain}"
        used_emails.add(work_email)
        terminated = not is_head and fake.chance(r, 0.12)
        termination_days_ago = r.randint(5, 700) if terminated else None
        hire_days_ago = (termination_days_ago or 0) + r.randint(60, 365 * 12)
        employee_id = f"{company.employee_id_prefix}{i + 1:05d}"
        people.append({
            "employee_id": employee_id, "first_name": first, "last_name": last, "country": country,
            "department": dept, "title": title, "grade": grade, "work_email": work_email,
            "hire_days_ago": hire_days_ago, "termination_days_ago": termination_days_ago,
            "is_head": is_head,
        })
    heads = {p["department"]["department_id"]: p["employee_id"] for p in people if p["is_head"]}
    ceo = people[0]["employee_id"]
    for p in people:
        p["manager_id"] = None if p["employee_id"] == ceo else ceo if p["is_head"] else heads[p["department"]["department_id"]]
    _employees[company.key] = people
    return people


def staff_in(company: Company, business_unit: str) -> list[dict]:
    """Current employees in a business unit."""
    return [p for p in employees(company) if p["department"]["business_unit"] == business_unit and not p["termination_days_ago"]]


def bronze(company: Company) -> list[Table]:
    people = employees(company)
    depts = departments(company)
    heads = {p["department"]["department_id"]: p["employee_id"] for p in people if p["is_head"]}
    meta = ("HRIS", "hris-nightly")

    department_rows = [
        (d["department_id"], d["department_name"], d["business_unit"], d["cost_centre"], heads[d["department_id"]], *meta)
        for d in depts
    ]

    r = fake.rng(company.key, "hr", "employee_details")
    employee_rows = []
    for p in people:
        country = p["country"]
        addr = fake.address(r, country)
        gender = fake.weighted(r, {"F": 49, "M": 49, "X": 2})
        raw_gender = r.choice({"F": ("F", "Female", "female"), "M": ("M", "Male", "male"), "X": ("X", "Non-binary")}[gender])
        if country == "AU":
            tax_id, tax_type = fake.tfn(r), "TFN"
        elif country == "NZ":
            tax_id, tax_type = f"{fake.digits(r, 3)}-{fake.digits(r, 3)}-{fake.digits(r, 3)}", "IRD"
        elif country == "SG":
            tax_id, tax_type = f"S{fake.digits(r, 7)}{r.choice('ABCDEFGHIZJ')}", "NRIC"
        else:
            tax_id, tax_type = f"QQ {fake.digits(r, 2)} {fake.digits(r, 2)} {fake.digits(r, 2)} {r.choice('ABCD')}", "NINO"
        employee_rows.append((
            p["employee_id"], p["first_name"], p["last_name"],
            p["first_name"][:3] if fake.chance(r, 0.1) else None,
            fake.birth_date(r, 21, 66), raw_gender,
            fake.email(r, p["first_name"], p["last_name"]), p["work_email"], fake.phone(r, country),
            addr["address_line"], addr["suburb"], addr["state"], addr["postcode"],
            r.choice({"AU": ("AU", "AU", "Australia"), "NZ": ("NZ", "New Zealand"), "SG": ("SG",), "GB": ("GB", "UK")}[country]),
            tax_id, tax_type,
            fake.bsb(r, "082") if country == "AU" else None, fake.digits(r, 8),
            p["department"]["department_id"], p["title"], p["manager_id"],
            fake.weighted(r, {"FULL_TIME": 80, "PART_TIME": 12, "CONTRACT": 8}),
            DaysAgo(p["hire_days_ago"]),
            DaysAgo(p["termination_days_ago"]) if p["termination_days_ago"] else None,
            r.choice(TERMINATION_REASONS) if p["termination_days_ago"] else None,
            r.choice(WORK_LOCATIONS[country]), *meta,
        ))

    r = fake.rng(company.key, "hr", "compensation")
    compensation_rows, current_salary = [], {}
    for p in people:
        low, high = SALARY_BANDS[p["grade"]]
        salary = Decimal(r.randint(low // 500, high // 500) * 500)
        currency = fake.CURRENCIES[p["country"]]
        if fake.chance(r, 0.4) and p["hire_days_ago"] > 400:
            previous = (salary * Decimal("0.95")).quantize(Decimal("1"))
            compensation_rows.append((None, p["employee_id"], DaysAgo(p["hire_days_ago"]), previous, currency,
                                      Decimal("10.0"), Decimal("11.0"), p["grade"], "New hire"))
            effective, reason = DaysAgo(r.randint(30, min(365, p["hire_days_ago"] - 1))), r.choice(("Annual review", "Promotion", "Market adjustment"))
        else:
            effective, reason = DaysAgo(p["hire_days_ago"]), "New hire"
        bonus = Decimal({"G8": "25.0", "G9": "40.0"}.get(p["grade"], "10.0"))
        compensation_rows.append((None, p["employee_id"], effective, salary, currency, bonus, Decimal("11.5"), p["grade"], reason))
        current_salary[p["employee_id"]] = (salary, currency)
    compensation_rows = [(f"CMP{i:06d}", *row[1:], *meta) for i, row in enumerate(compensation_rows, start=1)]

    r = fake.rng(company.key, "hr", "payroll")
    payroll_rows = []
    for p in people:
        if p["termination_days_ago"]:
            continue
        salary, currency = current_salary[p["employee_id"]]
        for days_ago in PAY_PERIOD_DAYS_AGO:
            if days_ago > p["hire_days_ago"]:
                continue
            gross = (salary / 26).quantize(Decimal("0.01"))
            tax = (gross * fake.rate(r, 0.22, 0.36)).quantize(Decimal("0.01"))
            payroll_rows.append((f"PAY{len(payroll_rows) + 1:06d}", p["employee_id"], DaysAgo(days_ago), gross, tax,
                                 (gross * Decimal("0.115")).quantize(Decimal("0.01")), gross - tax, currency, "PAYROLL", "pay-run"))

    r = fake.rng(company.key, "hr", "leave")
    leave_rows = []
    for i in range(int(company.staff * 1.6)):
        p = r.choice(people)
        leave_type = fake.weighted(r, {"ANNUAL": 50, "SICK": 30, "CARERS": 10, "PARENTAL": 4, "LONG_SERVICE": 6})
        days = {"ANNUAL": r.randint(1, 15), "SICK": r.randint(1, 4), "CARERS": r.randint(1, 3),
                "PARENTAL": r.randint(40, 120), "LONG_SERVICE": r.randint(20, 60)}[leave_type]
        start = r.randint(-45, 400)
        status = "APPROVED" if start > 0 else fake.weighted(r, {"APPROVED": 70, "PENDING": 30})
        leave_rows.append((f"LV{i + 1:06d}", p["employee_id"], leave_type, DaysAgo(start), DaysAgo(start - days),
                           Decimal(days), status, r.choice(LEAVE_REASONS[leave_type]), *meta))

    r = fake.rng(company.key, "hr", "reviews")
    review_rows = []
    for p in people:
        if p["manager_id"] is None or p["hire_days_ago"] < 200:
            continue
        rating = int(fake.weighted(r, {"5": 10, "4": 30, "3": 45, "2": 11, "1": 4}))
        text = REVIEW_TEXT[rating].format(first=p["first_name"], dept=p["department"]["department_name"])
        review_rows.append((f"RV{len(review_rows) + 1:06d}", p["employee_id"], p["manager_id"], "FY2026", rating, text, *meta))

    r = fake.rng(company.key, "hr", "emergency_contacts")
    contact_rows = []
    for p in people:
        first, last = fake.name(r)
        contact_rows.append((f"EC{len(contact_rows) + 1:06d}", p["employee_id"], f"{first} {last}",
                             r.choice(RELATIONSHIPS), fake.phone(r, p["country"]), *meta))

    m = meta_columns()
    return [
        Table("bronze_departments", "Departments and business units from the HR system (HRIS).", [
            Col("department_id", "string"), Col("department_name", "string"), Col("business_unit", "string"),
            Col("cost_centre", "string"), Col("head_employee_id", "string"), *m], department_rows),
        Table("bronze_employees", "Employee master records from the HR system (HRIS). Raw values: gender and country spellings vary.", [
            Col("employee_id", "string"), Col("first_name", "string", "Person name"), Col("last_name", "string", "Person name"),
            Col("preferred_name", "string"), Col("date_of_birth", "date", "PII: date of birth"),
            Col("gender", "string", "Sensitive: gender"), Col("personal_email", "string", "PII: personal email"),
            Col("work_email", "string"), Col("mobile_phone", "string", "PII: phone number"),
            Col("home_address", "string", "PII: home address"), Col("suburb", "string"), Col("state", "string"),
            Col("postcode", "string"), Col("country", "string"),
            Col("tax_id", "string", "Highly sensitive: national tax ID (TFN, IRD, NRIC or NI number)"),
            Col("tax_id_type", "string"), Col("bank_bsb", "string", "Financial: salary account BSB"),
            Col("bank_account_number", "string", "Financial: salary account number"),
            Col("department_id", "string"), Col("position_title", "string"), Col("manager_id", "string"),
            Col("employment_type", "string"), Col("hire_date", "date"), Col("termination_date", "date"),
            Col("termination_reason", "string", "Sensitive: reason for leaving"), Col("work_location", "string"), *m,
        ], employee_rows),
        Table("bronze_compensation", "Salary history from the HR system: one row per change.", [
            Col("comp_id", "string"), Col("employee_id", "string"), Col("effective_date", "date"),
            Col("base_salary", "decimal(12,2)", "Sensitive: salary, in local currency"), Col("currency", "string"),
            Col("bonus_target_pct", "decimal(5,1)"), Col("super_rate_pct", "decimal(5,1)"), Col("pay_grade", "string"),
            Col("change_reason", "string"), *m], compensation_rows),
        Table("bronze_payroll", "Payslips for the last four fortnightly pay runs, from the payroll system.", [
            Col("payslip_id", "string"), Col("employee_id", "string"), Col("pay_period_end", "date"),
            Col("gross_pay", "decimal(12,2)", "Sensitive: pay"), Col("tax_withheld", "decimal(12,2)"),
            Col("super_contribution", "decimal(12,2)"), Col("net_pay", "decimal(12,2)", "Sensitive: pay"),
            Col("currency", "string"), *m], payroll_rows),
        Table("bronze_leave_requests", "Leave requests from the HR system, past and upcoming.", [
            Col("leave_id", "string"), Col("employee_id", "string"), Col("leave_type", "string"),
            Col("start_date", "date"), Col("end_date", "date"), Col("days_taken", "decimal(5,1)"),
            Col("leave_status", "string"), Col("reason", "text", "Free text: may contain health information"), *m], leave_rows),
        Table("bronze_performance_reviews", "Annual performance reviews written by managers.", [
            Col("review_id", "string"), Col("employee_id", "string"), Col("reviewer_id", "string"),
            Col("review_period", "string"), Col("rating", "int", "1 (did not meet) to 5 (outstanding)"),
            Col("review_text", "text", "Free text: performance and sometimes health details"), *m], review_rows),
        Table("bronze_emergency_contacts", "Next of kin and emergency contacts.", [
            Col("contact_id", "string"), Col("employee_id", "string"), Col("contact_name", "string", "Person name"),
            Col("relationship", "string"), Col("phone", "string", "PII: phone number"), *m], contact_rows),
    ]


def silver() -> list[Derived]:
    def employees_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH base AS (
  SELECT
    e.employee_id,
    {d.initcap('TRIM(e.first_name)')} AS first_name,
    {d.initcap('TRIM(e.last_name)')} AS last_name,
    COALESCE(e.preferred_name, e.first_name) AS preferred_name,
    e.date_of_birth,
    {d.age('e.date_of_birth')} AS age,
    CASE UPPER(LEFT(TRIM(e.gender), 1)) WHEN 'F' THEN 'Female' WHEN 'M' THEN 'Male' ELSE 'Non-binary' END AS gender,
    LOWER(TRIM(e.personal_email)) AS personal_email,
    e.work_email,
    e.mobile_phone,
    e.home_address,
    e.suburb,
    e.state,
    e.postcode,
    {country_sql('e.country')} AS country,
    REGEXP_REPLACE(e.tax_id, '[^0-9A-Za-z]', '') AS tax_id,
    e.tax_id_type,
    e.bank_bsb,
    e.bank_account_number,
    e.department_id,
    d.department_name,
    d.business_unit,
    e.position_title,
    e.manager_id,
    e.employment_type,
    e.hire_date,
    e.termination_date,
    e.termination_reason,
    e.work_location,
    CASE WHEN e.termination_date IS NULL THEN TRUE ELSE FALSE END AS is_active,
    {d.years_between('e.hire_date', f'COALESCE(e.termination_date, {d.today})')} AS tenure_years
  FROM {s.ref('bronze_employees')} e
  LEFT JOIN {s.ref('bronze_departments')} d ON d.department_id = e.department_id
)
SELECT base.*, {region_sql('base.country')} AS region
FROM base"""

    def compensation_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH ranked AS (
  SELECT c.*, ROW_NUMBER() OVER (PARTITION BY c.employee_id ORDER BY c.effective_date DESC) AS rn
  FROM {s.ref('bronze_compensation')} c
)
SELECT
  c.comp_id,
  c.employee_id,
  c.effective_date,
  {d.money('c.base_salary')} AS base_salary,
  c.currency,
  {aud_sql('c.base_salary', 'c.currency', d.money)} AS base_salary_aud,
  c.bonus_target_pct,
  c.super_rate_pct,
  c.pay_grade,
  c.change_reason,
  CASE WHEN c.rn = 1 THEN TRUE ELSE FALSE END AS is_current,
  e.department_name,
  e.business_unit,
  e.gender,
  e.is_active,
  e.country,
  e.region
FROM ranked c
JOIN {s.ref('silver_employees')} e ON e.employee_id = c.employee_id"""

    def payroll_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  p.payslip_id,
  p.employee_id,
  p.pay_period_end,
  {d.money('p.gross_pay')} AS gross_pay,
  {d.money('p.tax_withheld')} AS tax_withheld,
  {d.money('p.super_contribution')} AS super_contribution,
  {d.money('p.net_pay')} AS net_pay,
  p.currency,
  {aud_sql('p.gross_pay', 'p.currency', d.money)} AS gross_pay_aud,
  e.department_name,
  e.business_unit,
  e.country,
  e.region
FROM {s.ref('bronze_payroll')} p
JOIN {s.ref('silver_employees')} e ON e.employee_id = p.employee_id"""

    def leave_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  l.leave_id,
  l.employee_id,
  l.leave_type,
  l.start_date,
  l.end_date,
  {d.month_start('l.start_date')} AS leave_month,
  l.days_taken,
  l.leave_status,
  l.reason,
  e.department_name,
  e.business_unit,
  e.country,
  e.region
FROM {s.ref('bronze_leave_requests')} l
JOIN {s.ref('silver_employees')} e ON e.employee_id = l.employee_id"""

    def reviews_sql(s: Sql) -> str:
        return f"""
SELECT
  v.review_id,
  v.employee_id,
  e.first_name || ' ' || e.last_name AS employee_name,
  v.reviewer_id,
  m.first_name || ' ' || m.last_name AS reviewer_name,
  v.review_period,
  v.rating,
  v.review_text,
  e.department_name,
  e.business_unit,
  e.country,
  e.region
FROM {s.ref('bronze_performance_reviews')} v
JOIN {s.ref('silver_employees')} e ON e.employee_id = v.employee_id
LEFT JOIN {s.ref('silver_employees')} m ON m.employee_id = v.reviewer_id"""

    return [
        Derived("silver_employees", "Cleaned employees with department, age, tenure, active flag and region.", employees_sql),
        Derived("silver_compensation", "Salary history with AUD equivalent; is_current marks each employee's current salary.", compensation_sql),
        Derived("silver_payroll", "Payslips with department, region and AUD equivalent.", payroll_sql),
        Derived("silver_leave_requests", "Leave requests with department, region and month.", leave_sql),
        Derived("silver_performance_reviews", "Performance reviews with employee and reviewer names.", reviews_sql),
    ]


def gold() -> list[Derived]:
    def headcount_sql(s: Sql) -> str:
        d = s.d
        year_ago = d.add_days(d.today, -365)
        leavers = f"SUM(CASE WHEN termination_date >= {year_ago} THEN 1 ELSE 0 END)"
        active = "SUM(CASE WHEN is_active THEN 1 ELSE 0 END)"
        return f"""
SELECT
  business_unit,
  department_name,
  region,
  country,
  {active} AS active_headcount,
  ROUND(AVG(CASE WHEN is_active THEN tenure_years END), 1) AS avg_tenure_years,
  SUM(CASE WHEN hire_date >= {year_ago} THEN 1 ELSE 0 END) AS hires_last_12_months,
  {leavers} AS leavers_last_12_months,
  {d.pct(leavers, active)} AS attrition_rate_pct
FROM {s.ref('silver_employees')}
GROUP BY 1, 2, 3, 4"""

    def pay_equity_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  pay_grade,
  business_unit,
  gender,
  region,
  COUNT(*) AS employees,
  {d.money('AVG(base_salary_aud)')} AS avg_base_salary_aud,
  MIN(base_salary_aud) AS min_base_salary_aud,
  MAX(base_salary_aud) AS max_base_salary_aud
FROM {s.ref('silver_compensation')}
WHERE is_current AND is_active
GROUP BY 1, 2, 3, 4"""

    def leave_summary_sql(s: Sql) -> str:
        return f"""
SELECT
  leave_month,
  leave_type,
  business_unit,
  region,
  COUNT(*) AS requests,
  SUM(CASE WHEN leave_status = 'APPROVED' THEN days_taken ELSE 0 END) AS approved_days,
  SUM(CASE WHEN leave_status = 'PENDING' THEN 1 ELSE 0 END) AS pending_requests
FROM {s.ref('silver_leave_requests')}
GROUP BY 1, 2, 3, 4"""

    def performance_sql(s: Sql) -> str:
        return f"""
SELECT
  review_period,
  business_unit,
  department_name,
  region,
  COUNT(*) AS reviews,
  ROUND(AVG(CAST(rating AS {s.d.type('decimal(4,2)')})), 2) AS avg_rating,
  SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END) AS high_performers,
  SUM(CASE WHEN rating <= 2 THEN 1 ELSE 0 END) AS low_performers
FROM {s.ref('silver_performance_reviews')}
GROUP BY 1, 2, 3, 4"""

    return [
        Derived("gold_headcount", "Active headcount, tenure, hires, leavers and attrition by department and region.", headcount_sql),
        Derived("gold_pay_equity", "Current salaries (AUD) by grade, business unit, gender and region, for pay equity analysis.", pay_equity_sql),
        Derived("gold_leave_summary", "Leave requests and approved days by month, type, business unit and region.", leave_summary_sql),
        Derived("gold_performance_summary", "Review ratings by department and region: averages and high and low performers.", performance_sql),
    ]


def script(company: Company) -> Script:
    return Script(
        path=f"{company.folder}/redshift/{company.key}_hr.sql",
        title=f"{company.name} - HR",
        description=(
            f"HR data for {company.name}: employees, salaries, payroll, leave, performance reviews "
            "and emergency contacts. Every company's HR data has the same structure, in its own "
            "schema of the hr database."
        ),
        platform="redshift",
        container="hr",
        schemas=[Schema(company.key, f"{company.name} HR", f"HR data for {company.name} from its HR and payroll systems.",
                        bronze(company), silver(), gold())],
    )
