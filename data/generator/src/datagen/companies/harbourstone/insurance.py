"""General (P&C) insurance: motor and home policies, insured vehicles and
properties, claims, claim notes, claim payments and fraud flags. About a
third of policyholders are also retail banking customers."""

from __future__ import annotations

from decimal import Decimal

from ... import fake, hr
from ...common import meta_columns, region_sql
from ...model import At, Col, DaysAgo, Derived, Schema, Sql, Table
from . import COMPANY, retail

PRODUCTS = {"MOTOR_COMPREHENSIVE": 38, "MOTOR_THIRD_PARTY": 12, "HOME_BUILDING": 22, "HOME_CONTENTS": 18, "LANDLORD": 10}
PERILS = {"MOTOR": {"COLLISION": 55, "THEFT": 10, "HAIL": 12, "GLASS": 15, "VANDALISM": 8},
          "HOME": {"STORM": 28, "FLOOD": 5, "FIRE": 3, "WATER_DAMAGE": 30, "BURGLARY": 18, "ACCIDENTAL_DAMAGE": 16}}
VEHICLES = (("Toyota", "Corolla"), ("Toyota", "RAV4"), ("Mazda", "CX-5"), ("Hyundai", "i30"), ("Ford", "Ranger"),
            ("Kia", "Sportage"), ("Tesla", "Model 3"), ("Mitsubishi", "Triton"), ("Subaru", "Outback"), ("Volkswagen", "Golf"))
REPAIRERS = ("Smash Repairs Express", "Precision Panel Works", "Rapid Glass", "Storm Restore Builders", "Dry Fix Restorations")
NOTES = {
    "COLLISION": ("Insured rear-ended at lights on {street}. Third party driver {third_party}, licence {licence}, admitted fault. Car towed to {repairer}.",
                  "Assessor inspected vehicle at {repairer}. Quote of {amount} dollars approved for panel and bumper repairs."),
    "THEFT": ("Vehicle stolen from driveway at {address} overnight. Police event number E{digits} obtained.",
              "Vehicle not recovered after 21 days. Proceeding to total loss settlement at agreed value."),
    "HAIL": ("Hail damage to roof and bonnet during the storm on the weekend. Customer sent photos from {phone}.",
             "Booked into hail repair centre. Paintless dent repair approved."),
    "GLASS": ("Windscreen cracked by a stone on the highway. Replacement booked with {repairer}.",
              "Windscreen replaced. Excess waived as glass-only claim."),
    "VANDALISM": ("Car keyed and mirror broken while parked in {suburb}. Customer suspects a neighbour.",
                  "No witnesses. Repair approved less excess."),
    "STORM": ("Roof tiles lifted in storm and water came into the main bedroom. Customer and two children staying with relatives.",
              "Builder from {repairer} attended for make safe. Tarp installed. Scope of works to follow."),
    "FLOOD": ("Creek broke its banks and water rose 40cm through the ground floor at {address}. Customer is distressed; elderly mother lives with them.",
              "Hydrologist report requested to confirm flood versus storm water. Emergency accommodation approved for two weeks."),
    "FIRE": ("Kitchen fire started from an unattended stove. Fire brigade attended. Customer treated for smoke inhalation at hospital.",
             "Loss adjuster appointed. Smoke damage throughout; contents inventory requested."),
    "WATER_DAMAGE": ("Burst flexi hose under the bathroom vanity. Water damage to flooring and the hallway.",
                     "{repairer} completed drying. Flooring replacement approved."),
    "BURGLARY": ("Break-in through the back door at {address} while the family was on holiday. Laptop, jewellery and a TV taken.",
                 "Customer provided receipts for the laptop and TV. Jewellery valuation still outstanding."),
    "ACCIDENTAL_DAMAGE": ("Customer dropped a heavy pot and cracked the stone benchtop.",
                          "Quote received for benchtop replacement. Approved less excess."),
}
FRAUD_INDICATORS = {
    "LATE_REPORTING": "Loss reported {days} days after the event with no explanation for the delay.",
    "MULTIPLE_CLAIMS": "Third claim in 12 months; previous two were also for theft of high-value items.",
    "INCONSISTENT_STATEMENT": "Statement of loss differs from the police report on the time and location of the incident.",
    "NEW_POLICY": "Claim lodged within 30 days of the policy starting, with sum insured increased just before the loss.",
}
COUNTRIES = {"AU": 86, "NZ": 12, "SG": 2}
# Annual premium as a share of sum insured, and typical claim sizes, so loss
# ratios land in a believable range (mostly 40 to 110 percent).
PREMIUM_RATES = {"MOTOR_COMPREHENSIVE": (0.025, 0.045), "HOME_BUILDING": (0.0015, 0.0035), "HOME_CONTENTS": (0.01, 0.018),
                 "LANDLORD": (0.002, 0.004)}
CLAIM_SIZES = {"COLLISION": (800, 12000), "THEFT": (8000, 45000), "HAIL": (1500, 9000), "GLASS": (300, 1200),
               "VANDALISM": (400, 3500), "STORM": (2000, 18000), "FLOOD": (15000, 90000), "FIRE": (15000, 120000),
               "WATER_DAMAGE": (1500, 12000), "BURGLARY": (1500, 12000), "ACCIDENTAL_DAMAGE": (400, 4000)}


def line(product: str) -> str:
    return "MOTOR" if product.startswith("MOTOR") else "HOME"


def bronze() -> list[Table]:
    m = meta_columns()
    meta = ("GUIDEWIRE", "gw-0412")

    r = fake.rng("harbourstone", "insurance", "policyholders")
    bank_customers = [c for c in retail.customers() if c["country"] in COUNTRIES]
    cross_sold = r.sample(bank_customers, 90)
    holders = []
    for i in range(400):
        if i < len(cross_sold):
            c = cross_sold[i]
            holder = {"first": c["first"], "last": c["last"], "dob": c["dob"], "email": c["email"], "phone": c["phone"],
                      "address": c["address"], "country": c["country"], "bank_id": c["id"]}
        else:
            country = fake.weighted(r, COUNTRIES)
            first, last = fake.name(r)
            holder = {"first": first, "last": last, "dob": fake.birth_date(r, 18, 85), "email": fake.email(r, first, last),
                      "phone": fake.phone(r, country), "address": fake.address(r, country), "country": country, "bank_id": None}
        holder["id"] = f"PH{400001 + i}"
        holder["licence"] = fake.drivers_licence(r)
        holders.append(holder)
    holder_rows = [
        (h["id"], h["first"], h["last"], h["dob"], h["email"], h["phone"], h["address"]["address_line"], h["address"]["suburb"],
         h["address"]["state"], h["address"]["postcode"], h["country"], h["licence"], h["bank_id"], *meta)
        for h in holders
    ]

    r = fake.rng("harbourstone", "insurance", "policies")
    policies = []
    for i in range(650):
        h = holders[i] if i < len(holders) else r.choice(holders)
        product = fake.weighted(r, PRODUCTS)
        start = r.randint(0, 700)
        end = start - 365
        status = "ACTIVE" if end < 0 else fake.weighted(r, {"EXPIRED": 50, "RENEWED": 35, "CANCELLED": 15})
        if end < 0 and fake.chance(r, 0.05):
            status = "CANCELLED"
        sum_insured = {"MOTOR": Decimal(r.randint(12, 90) * 1000), "HOME": Decimal(r.randint(30, 200) * 10000)}[line(product)]
        if product == "HOME_CONTENTS":
            sum_insured = Decimal(r.randint(30, 250) * 1000)
        premium = (sum_insured * fake.rate(r, *PREMIUM_RATES.get(product, (0.02, 0.04)), 4)).quantize(Decimal("0.01"))
        if product == "MOTOR_THIRD_PARTY":
            sum_insured, premium = Decimal("20000000"), fake.money(r, 280, 650)
        policies.append({"id": f"POL{700001 + i}", "holder": h, "product": product, "start": start, "end": end,
                         "status": status, "sum_insured": sum_insured, "premium": premium})
    policy_rows = [
        (p["id"], p["holder"]["id"], p["product"], DaysAgo(p["start"]), DaysAgo(p["end"]), p["sum_insured"], p["premium"],
         Decimal(r.choice((500, 750, 1000, 2000))), p["status"],
         "BANK_CROSS_SELL" if p["holder"]["bank_id"] else fake.weighted(r, {"DIRECT": 60, "BROKER": 30, "COMPARISON_SITE": 10}), *meta)
        for p in policies
    ]

    r = fake.rng("harbourstone", "insurance", "risks")
    vehicle_rows, property_rows = [], []
    for p in policies:
        if line(p["product"]) == "MOTOR":
            make, model = r.choice(VEHICLES)
            vehicle_rows.append((f"VEH{len(vehicle_rows) + 1:05d}", p["id"], fake.vin(r), fake.registration(r), make, model,
                                 r.randint(2008, 2026), p["holder"]["address"]["postcode"], *meta))
        else:
            a = p["holder"]["address"] if p["product"] != "LANDLORD" else fake.address(r, p["holder"]["country"])
            property_rows.append((f"PRP{len(property_rows) + 1:05d}", p["id"], a["address_line"], a["suburb"], a["state"],
                                  a["postcode"], p["holder"]["country"], fake.weighted(r, {"BRICK": 55, "TIMBER": 30, "CONCRETE": 15}),
                                  r.randint(1925, 2024), fake.chance(r, 0.12), fake.chance(r, 0.15), *meta))

    r = fake.rng("harbourstone", "insurance", "claims")
    assessors = hr.staff_in(COMPANY, "INSURANCE")
    claims = []
    for i in range(110):
        p = r.choice(policies)
        peril = fake.weighted(r, PERILS[line(p["product"])])
        loss = r.randint(max(p["end"], 0), p["start"]) if p["start"] > 0 else 0
        delay = r.randint(0, 5) if fake.chance(r, 0.85) else r.randint(20, 90)
        reported = max(loss - delay, 0)
        # Third party policies only pay for damage to other people's property.
        sizes = (400, 2500) if p["product"] == "MOTOR_THIRD_PARTY" else CLAIM_SIZES[peril]
        claimed = min(fake.money(r, *sizes), p["sum_insured"])
        status = "LODGED" if reported < 3 else fake.weighted(r, {"ASSESSING": 20, "APPROVED": 15, "SETTLED": 50, "DECLINED": 10, "WITHDRAWN": 5})
        claims.append({"id": f"CLM{800001 + i}", "policy": p, "peril": peril, "loss": loss, "reported": reported, "delay": delay,
                       "claimed": claimed, "status": status, "assessor": r.choice(assessors)["employee_id"]})
    claim_rows = [
        (c["id"], c["policy"]["id"], DaysAgo(c["loss"]), DaysAgo(c["reported"]), c["peril"], c["claimed"],
         c["claimed"] if c["status"] in ("LODGED", "ASSESSING", "APPROVED") else Decimal("0.00"), c["status"], c["assessor"], *meta)
        for c in claims
    ]

    r = fake.rng("harbourstone", "insurance", "notes")
    note_rows = []
    for c in claims:
        h = c["policy"]["holder"]
        first, last = fake.name(r)
        values = {"street": f"{r.choice(fake.STREETS)} {r.choice(fake.STREET_TYPES)}", "third_party": f"{first} {last}",
                  "licence": fake.drivers_licence(r), "repairer": r.choice(REPAIRERS), "amount": r.randint(15, 180) * 100,
                  "address": f"{h['address']['address_line']}, {h['address']['suburb']}", "digits": fake.digits(r, 8),
                  "phone": h["phone"], "suburb": h["address"]["suburb"]}
        first_note, follow_up = NOTES[c["peril"]]
        notes = [("CLAIMS_OFFICER", c["reported"], first_note)]
        if c["status"] != "LODGED":
            notes.append(("ASSESSOR", max(c["reported"] - r.randint(1, 10), 0), follow_up))
        for role, days_ago, template in notes:
            note_rows.append((f"NTE{len(note_rows) + 1:06d}", c["id"], At(days_ago, fake.minute_of_day(r, 8, 18)), role,
                              c["assessor"] if role == "ASSESSOR" else r.choice(assessors)["employee_id"], template.format(**values), *meta))

    r = fake.rng("harbourstone", "insurance", "payments")
    payment_rows = []
    for c in claims:
        if c["status"] not in ("SETTLED", "APPROVED"):
            continue
        h = c["policy"]["holder"]
        split = [Decimal("1.0")] if fake.chance(r, 0.7) else [Decimal("0.6"), Decimal("0.4")]
        for share in split:
            to_repairer = fake.chance(r, 0.5)
            payee = r.choice(REPAIRERS) + " Pty Ltd" if to_repairer else f"{h['first']} {h['last']}"
            amount = (c["claimed"] * share * fake.rate(r, 0.7, 1.0)).quantize(Decimal("0.01"))
            payment_rows.append((f"PMT{len(payment_rows) + 1:06d}", c["id"], DaysAgo(max(c["reported"] - r.randint(5, 40), 0)), amount,
                                 payee, fake.bsb(r, r.choice(("062", "033", "013", "083"))) if h["country"] == "AU" else None,
                                 fake.digits(r, 9), "EFT", *meta))

    r = fake.rng("harbourstone", "insurance", "fraud")
    fraud_rows = []
    suspicious = [c for c in claims if c["delay"] >= 20] + r.sample(claims, 25)
    for c in suspicious[:40]:
        indicator = "LATE_REPORTING" if c["delay"] >= 20 else r.choice(list(FRAUD_INDICATORS)[1:])
        fraud_rows.append((f"FRD{len(fraud_rows) + 1:05d}", c["id"], At(max(c["reported"] - 1, 0), fake.minute_of_day(r, 1, 4)),
                           indicator, r.randint(30, 95), FRAUD_INDICATORS[indicator].format(days=c["delay"]), *meta))

    return [
        Table("bronze_policyholders", "Policyholders from the policy administration system. bank_customer_id links cross-sold customers to retail banking.", [
            Col("policyholder_id", "string"), Col("first_name", "string", "Person name"), Col("last_name", "string", "Person name"),
            Col("date_of_birth", "date", "PII: date of birth"), Col("email", "string", "PII: email"),
            Col("phone", "string", "PII: phone number"), Col("address_line", "string", "PII: street address"),
            Col("suburb", "string"), Col("state", "string"), Col("postcode", "string"), Col("country", "string"),
            Col("drivers_licence_number", "string", "Highly sensitive: driver licence number"),
            Col("bank_customer_id", "string", "Matches customer_id in retail banking"), *m], holder_rows),
        Table("bronze_policies", "Motor and home policies. Policies run for 12 months from the start date.", [
            Col("policy_id", "string"), Col("policyholder_id", "string"), Col("product_code", "string"), Col("start_date", "date"),
            Col("end_date", "date"), Col("sum_insured", "decimal(14,2)"), Col("annual_premium", "decimal(12,2)"),
            Col("excess", "decimal(10,2)"), Col("policy_status", "string"), Col("sales_channel", "string"), *m], policy_rows),
        Table("bronze_vehicles", "Vehicles insured by motor policies.", [
            Col("vehicle_id", "string"), Col("policy_id", "string"), Col("vin", "string", "Vehicle identification number"),
            Col("registration", "string", "Number plate"), Col("make", "string"), Col("model", "string"), Col("build_year", "int"),
            Col("garaged_postcode", "string"), *m], vehicle_rows),
        Table("bronze_properties", "Properties insured by home and landlord policies, with natural hazard flags.", [
            Col("property_id", "string"), Col("policy_id", "string"), Col("address_line", "string", "PII: street address"),
            Col("suburb", "string"), Col("state", "string"), Col("postcode", "string"), Col("country", "string"),
            Col("construction_type", "string"), Col("year_built", "int"), Col("in_flood_zone", "bool"),
            Col("in_bushfire_zone", "bool"), *m], property_rows),
        Table("bronze_claims", "Claims from the claims system. reserve_amount is the expected cost still to pay.", [
            Col("claim_id", "string"), Col("policy_id", "string"), Col("loss_date", "date"), Col("reported_date", "date"),
            Col("peril", "string"), Col("claimed_amount", "decimal(14,2)"), Col("reserve_amount", "decimal(14,2)"),
            Col("claim_status", "string"), Col("assessor_employee_id", "string", "Matches employee_id in the HR data"), *m], claim_rows),
        Table("bronze_claim_notes", "File notes written by claims officers and assessors.", [
            Col("note_id", "string"), Col("claim_id", "string"), Col("note_ts", "timestamp"), Col("author_role", "string"),
            Col("author_employee_id", "string"),
            Col("note_text", "text", "Free text: names third parties, licence numbers, addresses and sometimes injuries"), *m], note_rows),
        Table("bronze_claim_payments", "Payments made on claims, to policyholders or repairers.", [
            Col("payment_id", "string"), Col("claim_id", "string"), Col("paid_date", "date"), Col("amount", "decimal(14,2)"),
            Col("payee_name", "string", "Person or business name"), Col("payee_bsb", "string", "Financial: BSB"),
            Col("payee_account_number", "string", "Financial: account number"), Col("payment_method", "string"), *m], payment_rows),
        Table("bronze_fraud_flags", "Fraud indicators raised on claims by the fraud detection rules.", [
            Col("flag_id", "string"), Col("claim_id", "string"), Col("flagged_at", "timestamp"), Col("indicator", "string"),
            Col("fraud_score", "int", "0 to 100"), Col("details", "text", "Free text: why the claim was flagged"), *m], fraud_rows),
    ]


def silver() -> list[Derived]:
    def holders_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  h.policyholder_id,
  {d.initcap('TRIM(h.first_name)')} AS first_name,
  {d.initcap('TRIM(h.last_name)')} AS last_name,
  h.date_of_birth,
  {d.age('h.date_of_birth')} AS age,
  LOWER(h.email) AS email,
  h.phone,
  h.address_line,
  h.suburb,
  h.state,
  h.postcode,
  h.country,
  {region_sql('h.country')} AS region,
  h.drivers_licence_number,
  h.bank_customer_id,
  CASE WHEN h.bank_customer_id IS NULL THEN FALSE ELSE TRUE END AS is_bank_customer
FROM {s.ref('bronze_policyholders')} h"""

    def policies_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  p.policy_id,
  p.policyholder_id,
  p.product_code,
  CASE WHEN p.product_code LIKE 'MOTOR%' THEN 'MOTOR' ELSE 'HOME' END AS product_line,
  p.start_date,
  p.end_date,
  p.sum_insured,
  p.annual_premium,
  p.excess,
  p.policy_status,
  CASE WHEN p.policy_status = 'ACTIVE' AND p.end_date >= {d.today} THEN TRUE ELSE FALSE END AS is_in_force,
  p.sales_channel,
  h.state,
  h.country,
  h.region
FROM {s.ref('bronze_policies')} p
JOIN {s.ref('silver_policyholders')} h ON h.policyholder_id = p.policyholder_id"""

    def vehicles_sql(s: Sql) -> str:
        return f"""
SELECT v.vehicle_id, v.policy_id, v.vin, UPPER(v.registration) AS registration, v.make, v.model, v.build_year,
       v.garaged_postcode, p.region
FROM {s.ref('bronze_vehicles')} v
JOIN {s.ref('silver_policies')} p ON p.policy_id = v.policy_id"""

    def properties_sql(s: Sql) -> str:
        return f"""
SELECT pr.property_id, pr.policy_id, pr.address_line, pr.suburb, pr.state, pr.postcode, pr.country,
       pr.construction_type, pr.year_built, pr.in_flood_zone, pr.in_bushfire_zone, p.region
FROM {s.ref('bronze_properties')} pr
JOIN {s.ref('silver_policies')} p ON p.policy_id = pr.policy_id"""

    def claims_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH paid AS (
  SELECT claim_id, SUM(amount) AS total_paid FROM {s.ref('bronze_claim_payments')} GROUP BY claim_id
)
SELECT
  c.claim_id,
  c.policy_id,
  p.policyholder_id,
  p.product_code,
  p.product_line,
  c.peril,
  c.loss_date,
  c.reported_date,
  {d.month_start('c.loss_date')} AS loss_month,
  {d.days_between('c.loss_date', 'c.reported_date')} AS days_to_report,
  c.claimed_amount,
  c.reserve_amount,
  COALESCE(pd.total_paid, 0) AS total_paid,
  COALESCE(pd.total_paid, 0) + c.reserve_amount AS incurred_amount,
  c.claim_status,
  CASE WHEN c.claim_status IN ('LODGED', 'ASSESSING', 'APPROVED') THEN TRUE ELSE FALSE END AS is_open,
  {d.days_between('c.reported_date', d.today)} AS days_since_reported,
  c.assessor_employee_id,
  p.state,
  p.country,
  p.region
FROM {s.ref('bronze_claims')} c
JOIN {s.ref('silver_policies')} p ON p.policy_id = c.policy_id
LEFT JOIN paid pd ON pd.claim_id = c.claim_id"""

    def notes_sql(s: Sql) -> str:
        return f"""
SELECT n.note_id, n.claim_id, n.note_ts, n.author_role, n.author_employee_id, n.note_text, c.peril, c.region
FROM {s.ref('bronze_claim_notes')} n
JOIN {s.ref('silver_claims')} c ON c.claim_id = n.claim_id"""

    def payments_sql(s: Sql) -> str:
        return f"""
SELECT pm.payment_id, pm.claim_id, pm.paid_date, pm.amount, pm.payee_name, pm.payee_bsb, pm.payee_account_number,
       pm.payment_method, c.region
FROM {s.ref('bronze_claim_payments')} pm
JOIN {s.ref('silver_claims')} c ON c.claim_id = pm.claim_id"""

    def fraud_sql(s: Sql) -> str:
        return f"""
SELECT f.flag_id, f.claim_id, f.flagged_at, f.indicator, f.fraud_score, f.details, c.region
FROM {s.ref('bronze_fraud_flags')} f
JOIN {s.ref('silver_claims')} c ON c.claim_id = f.claim_id"""

    return [
        Derived("silver_policyholders", "Policyholders with tidied names, age, region and whether they also bank with Harbourstone.", holders_sql),
        Derived("silver_policies", "Policies with product line, in-force flag and the policyholder's region.", policies_sql),
        Derived("silver_vehicles", "Insured vehicles with region.", vehicles_sql),
        Derived("silver_properties", "Insured properties with hazard flags and region.", properties_sql),
        Derived("silver_claims", "Claims with product, days to report, amounts paid and incurred, open flag and region.", claims_sql),
        Derived("silver_claim_notes", "Claim file notes with peril and region.", notes_sql),
        Derived("silver_claim_payments", "Claim payments with region.", payments_sql),
        Derived("silver_fraud_flags", "Fraud flags with region.", fraud_sql),
    ]


def gold() -> list[Derived]:
    def loss_ratio_sql(s: Sql) -> str:
        d = s.d
        year_ago = d.add_days(d.today, -365)
        return f"""
WITH premium AS (
  -- Earned premium: each policy's premium for the part of its term in the last 12 months.
  SELECT product_code, region, SUM(CASE WHEN is_in_force THEN 1 ELSE 0 END) AS policies_in_force,
         SUM(annual_premium * {d.days_between(f'GREATEST(start_date, {year_ago})', f'LEAST(end_date, {d.today})')} / 365) AS earned_premium
  FROM {s.ref('silver_policies')}
  WHERE start_date <= {d.today} AND end_date >= {year_ago} AND policy_status <> 'CANCELLED'
  GROUP BY product_code, region
),
losses AS (
  SELECT product_code, region, COUNT(*) AS claims, SUM(incurred_amount) AS incurred
  FROM {s.ref('silver_claims')}
  WHERE loss_date >= {year_ago} AND claim_status NOT IN ('DECLINED', 'WITHDRAWN')
  GROUP BY product_code, region
)
SELECT
  p.product_code,
  p.region,
  p.policies_in_force,
  {d.money('p.earned_premium')} AS earned_premium_12_months,
  COALESCE(l.claims, 0) AS claims_12_months,
  COALESCE(l.incurred, 0) AS incurred_claims_12_months,
  {d.pct('COALESCE(l.incurred, 0)', 'p.earned_premium')} AS loss_ratio_pct
FROM premium p
LEFT JOIN losses l ON l.product_code = p.product_code AND l.region = p.region"""

    def claims_overview_sql(s: Sql) -> str:
        return f"""
WITH latest_note AS (
  SELECT claim_id, note_text, ROW_NUMBER() OVER (PARTITION BY claim_id ORDER BY note_ts DESC) AS rn
  FROM {s.ref('silver_claim_notes')}
),
fraud AS (
  SELECT claim_id, COUNT(*) AS fraud_flags, MAX(fraud_score) AS max_fraud_score
  FROM {s.ref('silver_fraud_flags')}
  GROUP BY claim_id
)
SELECT
  c.claim_id,
  c.policy_id,
  c.product_code,
  c.product_line,
  c.peril,
  c.loss_date,
  c.reported_date,
  c.days_to_report,
  c.claim_status,
  c.is_open,
  c.days_since_reported,
  c.claimed_amount,
  c.total_paid,
  c.reserve_amount,
  c.incurred_amount,
  COALESCE(f.fraud_flags, 0) AS fraud_flags,
  f.max_fraud_score,
  n.note_text AS latest_note,
  c.state,
  c.country,
  c.region
FROM {s.ref('silver_claims')} c
LEFT JOIN fraud f ON f.claim_id = c.claim_id
LEFT JOIN latest_note n ON n.claim_id = c.claim_id AND n.rn = 1"""

    def exposure_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH weather_claims AS (
  SELECT policy_id, COUNT(*) AS weather_claims, SUM(incurred_amount) AS weather_incurred
  FROM {s.ref('silver_claims')}
  WHERE peril IN ('STORM', 'FLOOD', 'FIRE', 'HAIL') AND loss_date >= {d.add_days(d.today, -365)}
  GROUP BY policy_id
)
SELECT
  pr.country,
  pr.state,
  pr.region,
  pr.in_flood_zone,
  pr.in_bushfire_zone,
  COUNT(*) AS home_policies_in_force,
  SUM(p.sum_insured) AS total_sum_insured,
  SUM(COALESCE(w.weather_claims, 0)) AS weather_claims_12_months,
  SUM(COALESCE(w.weather_incurred, 0)) AS weather_incurred_12_months
FROM {s.ref('silver_properties')} pr
JOIN {s.ref('silver_policies')} p ON p.policy_id = pr.policy_id
LEFT JOIN weather_claims w ON w.policy_id = pr.policy_id
WHERE p.is_in_force
GROUP BY 1, 2, 3, 4, 5"""

    return [
        Derived("gold_loss_ratio", "Earned premium and claims incurred in the last 12 months, and the loss ratio, by product and region.", loss_ratio_sql),
        Derived("gold_claims_overview", "One row per claim: product, peril, status, amounts, fraud flags and the latest file note.", claims_overview_sql),
        Derived("gold_catastrophe_exposure", "In-force home cover by state and hazard zone, with weather claims in the last 12 months.", exposure_sql),
    ]


def schema() -> Schema:
    return Schema(
        "insurance",
        "Harbourstone Insurance",
        "General insurance: policyholders, motor and home policies, insured vehicles and properties, "
        "claims, claim notes, payments and fraud flags. Source: the policy and claims system (Guidewire).",
        bronze(), silver(), gold(),
    )
