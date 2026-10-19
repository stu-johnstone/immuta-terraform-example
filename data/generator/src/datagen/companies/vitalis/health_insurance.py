"""Private health insurance: members, policies with hospital and extras
cover, providers, claims and member contact notes. Some members are also
patients of Vitalis hospitals and dental clinics."""

from __future__ import annotations

from decimal import Decimal

from ... import fake, hr
from ...common import aud_sql, country_sql, meta_columns, region_sql
from ...model import At, Col, DaysAgo, Derived, Schema, Sql, Table
from . import CLINICS, COMPANY, HOSPITALS, RAW_COUNTRY, RAW_GENDER, age_band_sql, gender_sql

# Australian and New Zealand cover. Members living in Singapore, the UK or
# the US hold INTERNATIONAL (expatriate) cover instead.
PRODUCTS = {"HOSPITAL_GOLD": 18, "HOSPITAL_SILVER": 24, "HOSPITAL_BRONZE": 22, "HOSPITAL_BASIC": 12, "EXTRAS_ONLY": 14}
MONTHLY_PREMIUM = {"HOSPITAL_GOLD": (260, 340), "HOSPITAL_SILVER": (170, 240), "HOSPITAL_BRONZE": (120, 170),
                   "HOSPITAL_BASIC": (85, 120), "EXTRAS_ONLY": (35, 75), "INTERNATIONAL": (220, 420)}
MEMBERSHIP_TYPES = {"SINGLE": 40, "COUPLE": 25, "FAMILY": 28, "SINGLE_PARENT": 7}
PREMIUM_FACTOR = {"SINGLE": Decimal("1.0"), "COUPLE": Decimal("2.0"), "FAMILY": Decimal("2.1"), "SINGLE_PARENT": Decimal("1.6")}
COUNTRIES = {"AU": 80, "NZ": 12, "SG": 4, "GB": 2, "US": 2}
# The Australian Government rebate tier depends on income, so it is sensitive.
REBATE_TIERS = {"BASE": 60, "TIER_1": 18, "TIER_2": 12, "TIER_3": 10}
EXTERNAL_PROVIDERS = (
    ("Northbank Private Hospital", "HOSPITAL", "AU"), ("St Kilda Eye Surgery", "HOSPITAL", "AU"),
    ("Orchard Road Medical", "HOSPITAL", "SG"), ("Bayside Physiotherapy", "PHYSIOTHERAPIST", "AU"),
    ("CityMove Physio", "PHYSIOTHERAPIST", "AU"), ("Harbour Physio Auckland", "PHYSIOTHERAPIST", "NZ"),
    ("Lion City Physio", "PHYSIOTHERAPIST", "SG"), ("ClearSight Optometrists", "OPTOMETRIST", "AU"),
    ("Specs and Co", "OPTOMETRIST", "AU"), ("Kiwi Optical", "OPTOMETRIST", "NZ"), ("Align Chiropractic", "CHIROPRACTOR", "AU"),
    ("Mindful Psychology Clinic", "PSYCHOLOGIST", "AU"), ("Riverbank Psychology", "PSYCHOLOGIST", "AU"),
    ("Bright Smile Dental", "DENTIST", "AU"), ("Southern Cross Dental", "DENTIST", "AU"), ("Te Aro Smiles", "DENTIST", "NZ"),
    ("Pacific Hearing Centre", "AUDIOLOGIST", "AU"), ("Active Life Podiatry", "PODIATRIST", "AU"),
)
# Extras services by provider type, as (service code, description, charge range).
SERVICES = {
    "DENTIST": (("DENTAL_GENERAL", "General dental: check-up and clean", (120, 450)),
                ("DENTAL_MAJOR", "Major dental: crown or root canal", (900, 3500))),
    "OPTOMETRIST": (("OPTICAL", "Prescription glasses or contact lenses", (180, 650)),),
    "PHYSIOTHERAPIST": (("PHYSIO", "Physiotherapy consultation", (85, 140)),),
    "CHIROPRACTOR": (("CHIRO", "Chiropractic consultation", (70, 110)),),
    "PSYCHOLOGIST": (("PSYCHOLOGY", "Psychology session", (180, 260)),),
    "AUDIOLOGIST": (("HEARING_AIDS", "Hearing aids", (2500, 7000)),),
    "PODIATRIST": (("PODIATRY", "Podiatry consultation", (75, 120)),),
}
EXTRAS_WEIGHTS = {"DENTIST": 38, "OPTOMETRIST": 14, "PHYSIOTHERAPIST": 22, "CHIROPRACTOR": 8, "PSYCHOLOGIST": 10,
                  "AUDIOLOGIST": 2, "PODIATRIST": 6}
REJECTION_REASONS = ("Waiting period not served", "Annual limit reached", "Service not covered by this product",
                     "Membership in arrears")
INTERACTIONS = {
    "Claim enquiry": "Member called about claim {claim} for {service}. Explained the benefit and the gap of {gap} dollars. Identity verified with date of birth {dob}.",
    "Rejected claim": "Member upset that claim {claim} was rejected: {reason}. Member says the condition started after joining. Escalated to the benefits team.",
    "Pregnancy cover": "Member is {weeks} weeks pregnant and asked whether obstetrics is covered on {product}. Advised that a 12 month waiting period applies.",
    "Mental health": "Member disclosed a diagnosis of depression and anxiety and asked how many psychology sessions extras will cover this year. Limits sent to {email}.",
    "Surgery estimate": "Member has a knee replacement booked at {hospital} next month and asked about out-of-pocket costs. Estimate of {amount} dollars discussed.",
    "Payment update": "Member asked to change the direct debit to BSB {bsb} account {account}. Updated after verifying Medicare number {medicare}.",
    "Suspend cover": "Member travelling overseas for four months and asked to suspend cover. Mobile {phone} confirmed for the reminder before cover restarts.",
    "Add dependant": "Member asked to add newborn {child} to the policy. Birth certificate requested.",
    "Cancellation request": "Member wants to cancel because premiums went up again. Offered a downgrade to {cheaper}. Member will think about it.",
    "Address change": "Member moved to {address}. Records updated after verifying mobile {phone}.",
}
INTERACTION_WEIGHTS = {"Claim enquiry": 24, "Rejected claim": 8, "Pregnancy cover": 5, "Mental health": 6, "Surgery estimate": 8,
                       "Payment update": 12, "Suspend cover": 5, "Add dependant": 4, "Cancellation request": 10, "Address change": 18}
CHEAPER = {"HOSPITAL_GOLD": "Silver Hospital", "HOSPITAL_SILVER": "Bronze Hospital", "HOSPITAL_BRONZE": "Basic Hospital",
           "HOSPITAL_BASIC": "Extras Only", "EXTRAS_ONLY": "a lower extras limit", "INTERNATIONAL": "hospital-only international cover"}
META = ("MEMBERCORE", "mc-0412")

_book: dict | None = None


def book() -> dict:
    """Policies and members. Members are also used by hospitals and dental, as
    some are patients there."""
    global _book
    if _book is not None:
        return _book
    r = fake.rng("vitalis", "health_insurance", "policies")
    policies, members = [], []
    while len(members) < 330:
        country = fake.weighted(r, COUNTRIES)
        product = "INTERNATIONAL" if country in ("SG", "GB", "US") else fake.weighted(r, PRODUCTS)
        membership = fake.weighted(r, MEMBERSHIP_TYPES)
        start = r.randint(20, 365 * 15)
        address = fake.address(r, country)
        first, last = fake.name(r)
        people = [("PRIMARY", first, last, fake.birth_date(r, 25, 80))]
        if membership in ("COUPLE", "FAMILY"):
            partner_first, partner_last = fake.name(r)
            people.append(("PARTNER", partner_first, last if fake.chance(r, 0.6) else partner_last, fake.birth_date(r, 25, 80)))
        if membership in ("FAMILY", "SINGLE_PARENT"):
            for _ in range(r.randint(1, 3)):
                people.append(("DEPENDANT", fake.name(r)[0], last, fake.birth_date(r, 0, 20)))
        status = fake.weighted(r, {"ACTIVE": 86, "LAPSED": 5, "CANCELLED": 6, "SUSPENDED": 3})
        policy = {
            "id": f"VP{300001 + len(policies)}", "product": product, "membership": membership, "country": country,
            "start": start, "status": status, "end": r.randint(5, start - 1) if status in ("LAPSED", "CANCELLED") else None,
            "has_extras": product in ("EXTRAS_ONLY", "INTERNATIONAL") or fake.chance(r, 0.7),
            "medicare": fake.medicare_number(r) if country == "AU" else None,
        }
        policy["members"] = []
        for irn, (relationship, member_first, member_last, dob) in enumerate(people, start=1):
            adult = relationship != "DEPENDANT"
            age_days = (fake.REFERENCE_DATE - dob).days
            member = {
                "id": f"VM{500001 + len(members)}", "policy": policy, "relationship": relationship, "first": member_first,
                "last": member_last, "dob": dob, "gender": fake.weighted(r, {"F": 50, "M": 48, "X": 2}), "country": country,
                "address": address, "email": fake.email(r, member_first, member_last) if adult else None,
                "phone": fake.phone(r, country) if adult else None, "medicare_irn": irn if policy["medicare"] else None,
                "joined": start if adult else r.randint(20, max(21, min(start, age_days))),
            }
            policy["members"].append(member)
            members.append(member)
        policies.append(policy)
    _book = {"policies": policies, "members": members}
    return _book


def members() -> list[dict]:
    return book()["members"]


def bronze() -> list[Table]:
    from . import hospitals

    m = meta_columns()
    policies, people = book()["policies"], book()["members"]

    r = fake.rng("vitalis", "health_insurance", "member_rows")
    member_rows = []
    for p in people:
        a = p["address"]
        status = p["policy"]["status"]
        member_rows.append((
            p["id"], p["policy"]["id"], p["relationship"], p["first"].upper() if fake.chance(r, 0.08) else p["first"], p["last"],
            p["dob"], r.choice(RAW_GENDER[p["gender"]]), p["email"].upper() if p["email"] and fake.chance(r, 0.05) else p["email"],
            p["phone"], a["address_line"], a["suburb"], a["state"], a["postcode"], r.choice(RAW_COUNTRY[p["country"]]),
            p["policy"]["medicare"], p["medicare_irn"], DaysAgo(p["joined"]),
            r.choice((status.title(), status, status.lower())), *META,
        ))

    r = fake.rng("vitalis", "health_insurance", "policy_rows")
    policy_rows = []
    for p in policies:
        premium = (fake.money(r, *MONTHLY_PREMIUM[p["product"]]) * PREMIUM_FACTOR[p["membership"]]).quantize(Decimal("0.01"))
        payment = fake.weighted(r, {"DIRECT_DEBIT": 70, "CARD": 22, "PAYROLL": 8})
        debit = payment == "DIRECT_DEBIT"
        policy_rows.append((
            p["id"], p["members"][0]["id"], p["product"], p["membership"], p["has_extras"], DaysAgo(p["start"]),
            DaysAgo(p["end"]) if p["end"] else None, r.choice((p["status"].title(), p["status"], p["status"])),
            premium, fake.CURRENCIES[p["country"]],
            Decimal(r.choice((0, 250, 500, 750))) if p["product"] != "EXTRAS_ONLY" else Decimal("0"), payment,
            fake.bsb(r, r.choice(("062", "033", "083", COMPANY.bsb_prefix))) if debit and p["country"] == "AU" else None,
            fake.digits(r, 9) if debit else None, fake.card_number(r) if payment == "CARD" else None,
            fake.weighted(r, REBATE_TIERS) if p["country"] == "AU" else "NOT_APPLICABLE", *META,
        ))

    r = fake.rng("vitalis", "health_insurance", "providers")
    providers = [
        {"id": f"PRV{i:03d}", "name": h[1], "type": "HOSPITAL", "owned": True, "suburb": h[2], "state": h[4], "postcode": h[5], "country": h[6]}
        for i, h in enumerate(HOSPITALS, start=1)
    ]
    providers += [
        {"id": f"PRV{len(HOSPITALS) + i:03d}", "name": c[1], "type": "DENTIST", "owned": True, "suburb": c[2], "state": c[4],
         "postcode": c[5], "country": c[6]}
        for i, c in enumerate(CLINICS, start=1)
    ]
    for name, provider_type, country in EXTERNAL_PROVIDERS:
        a = fake.address(r, country)
        providers.append({"id": f"PRV{len(providers) + 1:03d}", "name": name, "type": provider_type, "owned": False,
                          "suburb": a["suburb"], "state": a["state"], "postcode": a["postcode"], "country": country})
    provider_rows = [
        (p["id"], p["name"], p["type"], p["owned"], f"{fake.digits(r, 6)}{r.choice('ABCDEFHJKLTWXY')}", p["suburb"], p["state"],
         p["postcode"], p["country"], *META)
        for p in providers
    ]

    r = fake.rng("vitalis", "health_insurance", "claims")
    claimable = [p for p in people if p["policy"]["status"] in ("ACTIVE", "SUSPENDED")]
    claims = []
    while len(claims) < 950:
        member = r.choice(claimable)
        policy = member["policy"]
        hospital_cover = policy["product"] != "EXTRAS_ONLY"
        if hospital_cover and (not policy["has_extras"] or fake.chance(r, 0.12)):
            if member["relationship"] == "DEPENDANT":
                continue
            diagnosis = r.choices(hospitals.DIAGNOSES, weights=[d[7] for d in hospitals.DIAGNOSES])[0]
            claim_type, service_code, description = "HOSPITAL", "HOSP_ADMISSION", diagnosis[3]
            charged = fake.money(r, *diagnosis[6])
            provider_type, diagnosis_code = "HOSPITAL", diagnosis[0]
            benefit_rate = (0.55, 0.75) if policy["product"] == "HOSPITAL_BASIC" else (0.85, 0.98)
        else:
            provider_type = fake.weighted(r, EXTRAS_WEIGHTS)
            service_code, description, charge_range = r.choice(SERVICES[provider_type])
            claim_type, diagnosis_code = "EXTRAS", None
            charged = fake.money(r, *charge_range)
            benefit_rate = (0.45, 0.75)
        options = [p for p in providers if p["type"] == provider_type and p["country"] == member["country"]]
        options = options or [p for p in providers if p["type"] == provider_type and p["country"] == "AU"]
        owned = [p for p in options if p["owned"]]
        provider = r.choice(owned) if owned and fake.chance(r, 0.55) else r.choice(options)
        if provider["owned"] and claim_type == "EXTRAS":
            benefit_rate = (0.75, 1.0)  # little or no gap at Vitalis' own clinics
        service = r.randint(0, min(365, policy["start"] - 1))
        channel = fake.weighted(r, {"HICAPS": 55, "ONLINE": 25, "APP": 15, "MAIL": 5}) if claim_type == "EXTRAS" else "PROVIDER"
        lodged = service if channel == "HICAPS" else max(service - r.randint(0, 20), 0)
        status = "PENDING" if lodged < 3 and channel != "HICAPS" else fake.weighted(r, {"PAID": 93, "REJECTED": 7})
        benefit = None if status == "PENDING" else Decimal("0.00") if status == "REJECTED" else \
            (charged * fake.rate(r, *benefit_rate)).quantize(Decimal("0.01"))
        claims.append([
            f"CL{6000001 + len(claims)}", policy["id"], member["id"], provider["id"], DaysAgo(service), claim_type, service_code,
            description, diagnosis_code, charged, benefit, fake.CURRENCIES[member["country"]], status,
            r.choice(REJECTION_REASONS) if status == "REJECTED" else None, channel,
            At(lodged, fake.minute_of_day(r, 8, 20)), *META,
        ])
    # The claims extract re-sends some claims; silver removes the duplicates.
    duplicates = [list(c) for c in r.sample(claims, 12)]
    for c in duplicates:
        c[-1] = "mc-0413"
    claim_rows = [tuple(c) for c in claims + duplicates]

    r = fake.rng("vitalis", "health_insurance", "interactions")
    staff = hr.staff_in(COMPANY, "HEALTH_INSURANCE")
    adults = [p for p in people if p["relationship"] != "DEPENDANT"]
    claims_by_member: dict[str, list] = {}
    for c in claims:
        claims_by_member.setdefault(c[2], []).append(c)
    product_names = {"HOSPITAL_GOLD": "Gold Hospital", "HOSPITAL_SILVER": "Silver Hospital", "HOSPITAL_BRONZE": "Bronze Hospital",
                     "HOSPITAL_BASIC": "Basic Hospital", "EXTRAS_ONLY": "Extras Only", "INTERNATIONAL": "International cover"}
    interaction_rows = []
    for i in range(260):
        member = r.choice(adults)
        policy = member["policy"]
        reason = fake.weighted(r, INTERACTION_WEIGHTS)
        member_claims = claims_by_member.get(member["id"], [])
        rejected = [c for c in member_claims if c[12] == "REJECTED"]
        if (reason == "Claim enquiry" and not member_claims) or (reason == "Rejected claim" and not rejected):
            reason = "Address change"
        if reason in ("Payment update", "Pregnancy cover") and policy["country"] != "AU":
            reason = "Suspend cover"
        claim = r.choice(rejected if reason == "Rejected claim" else member_claims) if member_claims else None
        a = fake.address(r, member["country"])
        gap = claim[9] - claim[10] if claim and claim[10] is not None else Decimal("0.00")
        values = {
            "claim": claim[0] if claim else "", "service": claim[7].lower() if claim else "", "gap": gap,
            "reason": claim[13].lower() if claim and claim[13] else "", "dob": member["dob"].strftime("%d/%m/%Y"),
            "weeks": r.randint(6, 30), "product": product_names[policy["product"]], "email": member["email"],
            "hospital": r.choice(HOSPITALS)[1], "amount": r.randint(5, 40) * 100, "bsb": fake.bsb(r, r.choice(("062", "033"))),
            "account": fake.digits(r, 9), "medicare": policy["medicare"] or "", "phone": member["phone"],
            "child": f"{fake.name(r)[0]} {member['last']}", "cheaper": CHEAPER[policy["product"]],
            "address": f"{a['address_line']}, {a['suburb']} {a['state']} {a['postcode']}",
        }
        interaction_rows.append((
            f"INT{i + 1:06d}", member["id"], At(fake.days_back(r, 0, 180), fake.minute_of_day(r, 8, 20)),
            fake.weighted(r, {"PHONE": 60, "CHAT": 20, "EMAIL": 12, "RETAIL_CENTRE": 8}), reason, r.choice(staff)["employee_id"],
            INTERACTIONS[reason].format(**values), *META,
        ))

    return [
        Table("bronze_members", "Everyone covered by a policy: the primary member, partners and dependants. Families share a Medicare card.", [
            Col("member_id", "string"), Col("policy_id", "string"), Col("relationship", "string", "PRIMARY, PARTNER or DEPENDANT"),
            Col("first_name", "string", "Person name"), Col("last_name", "string", "Person name"),
            Col("date_of_birth", "date", "PII: date of birth"), Col("gender", "string"), Col("email", "string", "PII: email"),
            Col("mobile_phone", "string", "PII: phone number"), Col("address_line", "string", "PII: street address"),
            Col("suburb", "string"), Col("state", "string"), Col("postcode", "string"),
            Col("country", "string", "Raw country as entered: AU, AUS, Australia..."),
            Col("medicare_number", "string", "Highly sensitive: Medicare card number (Australian members)"),
            Col("medicare_irn", "int", "Position on the Medicare card"), Col("joined_date", "date"), Col("member_status", "string"),
            *m], member_rows),
        Table("bronze_policies", "Health insurance policies: hospital cover, extras or both, for a single, couple or family.", [
            Col("policy_id", "string"), Col("primary_member_id", "string"), Col("product_code", "string"),
            Col("membership_type", "string"), Col("has_extras", "bool"), Col("start_date", "date"), Col("end_date", "date"),
            Col("policy_status", "string"), Col("monthly_premium", "decimal(10,2)"), Col("currency", "string"),
            Col("hospital_excess", "decimal(10,2)"), Col("payment_method", "string"), Col("debit_bsb", "string", "Financial: BSB"),
            Col("debit_account_number", "string", "Financial: account number"), Col("card_number", "string", "Financial: card number"),
            Col("rebate_tier", "string", "Sensitive: Australian Government rebate tier, which depends on income"), *m], policy_rows),
        Table("bronze_providers", "Hospitals and extras providers that claims are made at, including Vitalis' own hospitals and dental clinics.", [
            Col("provider_id", "string"), Col("provider_name", "string"), Col("provider_type", "string"),
            Col("is_vitalis_owned", "bool"), Col("provider_number", "string"), Col("suburb", "string"), Col("state", "string"),
            Col("postcode", "string"), Col("country", "string"), *m], provider_rows),
        Table("bronze_claims", "Hospital and extras claims for the last 12 months. benefit_amount is empty while a claim is pending.", [
            Col("claim_id", "string"), Col("policy_id", "string"), Col("member_id", "string"), Col("provider_id", "string"),
            Col("service_date", "date"), Col("claim_type", "string", "HOSPITAL or EXTRAS"), Col("service_code", "string"),
            Col("item_description", "string"),
            Col("diagnosis_code", "string", "Health information: ICD-10-AM diagnosis code for hospital claims"),
            Col("charged_amount", "decimal(12,2)"), Col("benefit_amount", "decimal(12,2)"), Col("currency", "string"),
            Col("claim_status", "string"), Col("rejection_reason", "string"), Col("lodgement_channel", "string"),
            Col("lodged_at", "timestamp"), *m], claim_rows),
        Table("bronze_member_interactions", "Contact centre and retail centre notes about members.", [
            Col("interaction_id", "string"), Col("member_id", "string"), Col("interaction_ts", "timestamp"),
            Col("channel", "string"), Col("reason", "string"),
            Col("staff_employee_id", "string", "Matches employee_id in the HR data"),
            Col("notes", "text", "Free text: health conditions, pregnancy, Medicare numbers, bank details, addresses and phone numbers"),
            *m], interaction_rows),
    ]


def silver() -> list[Derived]:
    def members_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH base AS (
  SELECT
    m.member_id,
    m.policy_id,
    m.relationship,
    {d.initcap('TRIM(m.first_name)')} AS first_name,
    {d.initcap('TRIM(m.last_name)')} AS last_name,
    m.date_of_birth,
    {d.age('m.date_of_birth')} AS age,
    {gender_sql('m.gender')} AS gender,
    LOWER(TRIM(m.email)) AS email,
    m.mobile_phone,
    m.address_line,
    m.suburb,
    m.state,
    m.postcode,
    {country_sql('m.country')} AS country,
    REGEXP_REPLACE(m.medicare_number, '[^0-9]', '') AS medicare_number,
    m.medicare_irn,
    m.joined_date,
    UPPER(TRIM(m.member_status)) AS member_status
  FROM {s.ref('bronze_members')} m
)
SELECT
  base.*,
  {age_band_sql('base.age')} AS age_band,
  {region_sql('base.country')} AS region
FROM base"""

    def policies_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH base AS (
  SELECT p.*, UPPER(TRIM(p.policy_status)) AS clean_status
  FROM {s.ref('bronze_policies')} p
)
SELECT
  p.policy_id,
  p.primary_member_id,
  p.product_code,
  CASE p.product_code WHEN 'HOSPITAL_GOLD' THEN 'Gold Hospital' WHEN 'HOSPITAL_SILVER' THEN 'Silver Hospital'
    WHEN 'HOSPITAL_BRONZE' THEN 'Bronze Hospital' WHEN 'HOSPITAL_BASIC' THEN 'Basic Hospital'
    WHEN 'EXTRAS_ONLY' THEN 'Extras Only' ELSE 'International Health Cover' END AS product_name,
  CASE WHEN p.product_code = 'EXTRAS_ONLY' THEN FALSE ELSE TRUE END AS has_hospital_cover,
  p.has_extras,
  p.membership_type,
  p.start_date,
  p.end_date,
  p.clean_status AS policy_status,
  CASE WHEN p.clean_status = 'ACTIVE' THEN TRUE ELSE FALSE END AS is_active,
  {d.years_between('p.start_date', f'COALESCE(p.end_date, {d.today})')} AS tenure_years,
  p.monthly_premium,
  p.currency,
  {aud_sql('p.monthly_premium', 'p.currency', d.money)} AS monthly_premium_aud,
  {aud_sql('p.monthly_premium * 12', 'p.currency', d.money)} AS annual_premium_aud,
  p.hospital_excess,
  p.payment_method,
  p.debit_bsb,
  p.debit_account_number,
  p.card_number,
  p.rebate_tier,
  m.state,
  m.country,
  m.region
FROM base p
JOIN {s.ref('silver_members')} m ON m.member_id = p.primary_member_id"""

    def providers_sql(s: Sql) -> str:
        return f"""
SELECT provider_id, provider_name, provider_type, is_vitalis_owned, provider_number, suburb, state, postcode, country,
       {region_sql('country')} AS region
FROM {s.ref('bronze_providers')}"""

    def claims_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH deduplicated AS (
  -- The extract re-sends some claims: keep the latest copy of each.
  SELECT c.*, ROW_NUMBER() OVER (PARTITION BY c.claim_id ORDER BY c._batch_id DESC) AS rn
  FROM {s.ref('bronze_claims')} c
)
SELECT
  c.claim_id,
  c.policy_id,
  c.member_id,
  c.provider_id,
  pr.provider_name,
  pr.provider_type,
  pr.is_vitalis_owned AS is_vitalis_provider,
  c.service_date,
  {d.month_start('c.service_date')} AS service_month,
  c.claim_type,
  c.service_code,
  c.item_description,
  c.diagnosis_code,
  c.charged_amount,
  c.benefit_amount,
  c.charged_amount - c.benefit_amount AS gap_amount,
  c.currency,
  {aud_sql('c.charged_amount', 'c.currency', d.money)} AS charged_aud,
  {aud_sql('c.benefit_amount', 'c.currency', d.money)} AS benefit_aud,
  {aud_sql('c.charged_amount - c.benefit_amount', 'c.currency', d.money)} AS gap_aud,
  c.claim_status,
  c.rejection_reason,
  c.lodgement_channel,
  c.lodged_at,
  {d.days_between('c.service_date', 'c.lodged_at')} AS days_to_lodge,
  p.product_code,
  m.age_band,
  m.gender,
  m.country,
  m.region
FROM deduplicated c
JOIN {s.ref('silver_members')} m ON m.member_id = c.member_id
JOIN {s.ref('silver_policies')} p ON p.policy_id = c.policy_id
JOIN {s.ref('silver_providers')} pr ON pr.provider_id = c.provider_id
WHERE c.rn = 1"""

    def interactions_sql(s: Sql) -> str:
        return f"""
SELECT i.interaction_id, i.member_id, i.interaction_ts, CAST(i.interaction_ts AS DATE) AS interaction_date, i.channel, i.reason,
       i.staff_employee_id, i.notes, m.country, m.region
FROM {s.ref('bronze_member_interactions')} i
JOIN {s.ref('silver_members')} m ON m.member_id = i.member_id"""

    return [
        Derived("silver_members", "Members with tidied names, age and age band, gender, ISO country, region and Medicare number digits only.", members_sql),
        Derived("silver_policies", "Policies with product name, active flag, tenure, AUD premiums and the primary member's region.", policies_sql),
        Derived("silver_providers", "Providers with region.", providers_sql),
        Derived("silver_claims", "Claims without duplicates, with provider, gap, AUD amounts, days to lodge and the member's region.", claims_sql),
        Derived("silver_member_interactions", "Member contact notes with region.", interactions_sql),
    ]


def gold() -> list[Derived]:
    def claims_monthly_sql(s: Sql) -> str:
        d = s.d
        paid = "claim_status = 'PAID'"
        return f"""
SELECT
  service_month,
  claim_type,
  service_code,
  region,
  COUNT(*) AS claims,
  COUNT(DISTINCT member_id) AS members_claiming,
  SUM(charged_aud) AS charged_aud,
  SUM(CASE WHEN {paid} THEN benefit_aud ELSE 0 END) AS benefits_paid_aud,
  SUM(CASE WHEN {paid} THEN gap_aud ELSE 0 END) AS member_gap_aud,
  {d.pct(f'SUM(CASE WHEN {paid} THEN benefit_aud ELSE 0 END)', f'SUM(CASE WHEN {paid} THEN charged_aud ELSE 0 END)')} AS benefit_pct,
  SUM(CASE WHEN claim_status = 'REJECTED' THEN 1 ELSE 0 END) AS rejected_claims,
  SUM(CASE WHEN claim_status = 'PENDING' THEN 1 ELSE 0 END) AS pending_claims
FROM {s.ref('silver_claims')}
GROUP BY 1, 2, 3, 4"""

    def member_360_sql(s: Sql) -> str:
        d = s.d
        paid = "claim_status = 'PAID'"
        return f"""
WITH claims AS (
  SELECT
    member_id,
    COUNT(*) AS claims_12_months,
    SUM(CASE WHEN claim_type = 'HOSPITAL' THEN 1 ELSE 0 END) AS hospital_claims_12_months,
    SUM(CASE WHEN {paid} THEN benefit_aud ELSE 0 END) AS benefits_paid_12_months_aud,
    SUM(CASE WHEN {paid} THEN gap_aud ELSE 0 END) AS gap_12_months_aud,
    SUM(CASE WHEN claim_status = 'REJECTED' THEN 1 ELSE 0 END) AS rejected_claims_12_months
  FROM {s.ref('silver_claims')}
  WHERE service_date >= {d.add_days(d.today, -365)}
  GROUP BY member_id
),
latest_contact AS (
  SELECT member_id, interaction_date, reason, notes,
         ROW_NUMBER() OVER (PARTITION BY member_id ORDER BY interaction_ts DESC) AS rn
  FROM {s.ref('silver_member_interactions')}
)
SELECT
  m.member_id,
  m.policy_id,
  m.first_name,
  m.last_name,
  m.relationship,
  m.age,
  m.age_band,
  m.gender,
  p.product_code,
  p.product_name,
  p.membership_type,
  p.has_extras,
  p.policy_status,
  p.tenure_years,
  p.monthly_premium_aud,
  COALESCE(c.claims_12_months, 0) AS claims_12_months,
  COALESCE(c.hospital_claims_12_months, 0) AS hospital_claims_12_months,
  COALESCE(c.benefits_paid_12_months_aud, 0) AS benefits_paid_12_months_aud,
  COALESCE(c.gap_12_months_aud, 0) AS gap_12_months_aud,
  COALESCE(c.rejected_claims_12_months, 0) AS rejected_claims_12_months,
  l.interaction_date AS last_contact_date,
  l.reason AS last_contact_reason,
  l.notes AS last_contact_note,
  m.state,
  m.country,
  m.region
FROM {s.ref('silver_members')} m
JOIN {s.ref('silver_policies')} p ON p.policy_id = m.policy_id
LEFT JOIN claims c ON c.member_id = m.member_id
LEFT JOIN latest_contact l ON l.member_id = m.member_id AND l.rn = 1"""

    def cover_mix_sql(s: Sql) -> str:
        return f"""
WITH covered AS (
  SELECT policy_id, COUNT(*) AS members FROM {s.ref('silver_members')} GROUP BY policy_id
)
SELECT
  p.product_code,
  p.product_name,
  p.membership_type,
  p.rebate_tier,
  p.region,
  COUNT(*) AS active_policies,
  SUM(c.members) AS members_covered,
  SUM(CASE WHEN p.has_extras THEN 1 ELSE 0 END) AS policies_with_extras,
  ROUND(AVG(p.monthly_premium_aud), 2) AS avg_monthly_premium_aud,
  SUM(p.annual_premium_aud) AS annual_premium_aud
FROM {s.ref('silver_policies')} p
JOIN covered c ON c.policy_id = p.policy_id
WHERE p.is_active
GROUP BY 1, 2, 3, 4, 5"""

    return [
        Derived("gold_claims_monthly", "Claims by month, claim type, service and region: claims, members claiming, charges, benefits paid, gap and rejections, in AUD.", claims_monthly_sql),
        Derived("gold_member_360", "One row per member: cover, claims, benefits and gap in the last 12 months, and the last contact note.", member_360_sql),
        Derived("gold_cover_mix", "Active policies by product, membership type, rebate tier and region, with members covered and AUD premiums.", cover_mix_sql),
    ]


def schema() -> Schema:
    return Schema(
        "health_insurance",
        "Vitalis Health Insurance",
        "Private health insurance: members, policies with hospital and extras cover, providers, claims and "
        "member contact notes. Source: the membership and claims system (MemberCore).",
        bronze(), silver(), gold(),
    )
