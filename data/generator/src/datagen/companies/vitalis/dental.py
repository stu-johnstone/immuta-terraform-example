"""Dental clinics: clinics, patients, appointments, treatments and clinical
notes. About a third of patients are Vitalis health insurance members."""

from __future__ import annotations

from decimal import Decimal

from ... import fake, hr
from ...common import aud_sql, country_sql, meta_columns, region_sql
from ...model import At, Col, DaysAgo, Derived, Schema, Sql, Table
from . import CLINICS, COMPANY, RAW_COUNTRY, RAW_GENDER, age_band_sql, gender_sql, health_insurance

# (item number, description, fee range, category, tooth specific)
ITEMS = {
    "011": ("Comprehensive oral examination", (70, 95), "PREVENTIVE", False),
    "012": ("Periodic oral examination", (55, 75), "PREVENTIVE", False),
    "114": ("Removal of calculus (scale and clean)", (110, 150), "PREVENTIVE", False),
    "121": ("Topical fluoride", (35, 50), "PREVENTIVE", False),
    "022": ("Intraoral radiograph", (40, 60), "DIAGNOSTIC", True),
    "311": ("Removal of a tooth", (180, 280), "GENERAL", True),
    "521": ("Adhesive restoration, one surface", (150, 220), "GENERAL", True),
    "522": ("Adhesive restoration, two surfaces", (200, 280), "GENERAL", True),
    "415": ("Root canal obturation", (400, 700), "MAJOR", True),
    "615": ("Full crown, ceramic", (1400, 2100), "MAJOR", True),
    "688": ("Implant crown", (2500, 3600), "MAJOR", True),
}
APPOINTMENT_TYPES = {"CHECK_UP": 40, "HYGIENE": 18, "TREATMENT": 27, "EMERGENCY": 8, "CONSULT": 7}
DURATION = {"CHECK_UP": 30, "HYGIENE": 45, "TREATMENT": 60, "EMERGENCY": 30, "CONSULT": 30}
MEDICAL_ALERTS = {"": 55, "Penicillin allergy": 8, "Anticoagulant: warfarin": 6, "Type 2 diabetes": 8, "Pregnant": 4,
                  "Heart valve replacement: antibiotic cover required": 3, "Asthma": 8, "Bisphosphonates for osteoporosis": 3,
                  "Dental anxiety": 5}
OTHER_FUNDS = {"Bluegum Health Fund": 30, "Southern Health Mutual": 20, "": 50}
CANCELLATION_REASONS = ("Patient unwell", "Work commitments", "Rescheduled online", "Clinic cancelled: dentist unavailable")
TEETH = [q * 10 + n for q in (1, 2, 3, 4) for n in range(1, 9)]  # FDI tooth numbers
META = ("DENTALPRO", "dp-0412")


def patients() -> list[dict]:
    r = fake.rng("vitalis", "dental", "patients")
    members = [m for m in health_insurance.members() if m["country"] in ("AU", "NZ") and m["policy"]["has_extras"]]
    result = []
    for i, member in enumerate(r.sample(members, 100) + [None] * 200):
        if member:
            person = {k: member[k] for k in ("first", "last", "dob", "gender", "email", "phone", "address", "country")}
            person.update(fund="Vitalis Health Insurance", fund_member_id=member["id"])
        else:
            country = fake.weighted(r, {"AU": 85, "NZ": 15})
            first, last = fake.name(r)
            fund = fake.weighted(r, OTHER_FUNDS)
            person = {"first": first, "last": last, "dob": fake.birth_date(r, 3, 90), "gender": fake.weighted(r, {"F": 52, "M": 47, "X": 1}),
                      "email": fake.email(r, first, last), "phone": fake.phone(r, country), "address": fake.address(r, country),
                      "country": country, "fund": fund, "fund_member_id": fake.digits(r, 8) if fund else None}
        person["id"] = f"DP{600001 + i}"
        person["age"] = (fake.REFERENCE_DATE - person["dob"]).days // 365
        person["guardian"] = f"{fake.name(r)[0]} {person['last']}" if person["age"] < 18 else None
        if person["age"] < 18:
            person["email"] = fake.email(r, person["guardian"].split()[0], person["last"])
            person["phone"] = fake.phone(r, person["country"])
        elif not person["email"]:  # dependants on a policy who are now adults
            person["email"] = fake.email(r, person["first"], person["last"])
            person["phone"] = fake.phone(r, person["country"])
        alert = fake.weighted(r, MEDICAL_ALERTS)
        if alert == "Pregnant" and (person["gender"] != "F" or not 18 <= person["age"] <= 45):
            alert = ""
        person["alert"] = alert
        local = [c for c in CLINICS if c[6] == person["country"]]
        person["clinic"] = r.choice(local)
        person["registered"] = r.randint(400, 365 * 12)
        result.append(person)
    return result


def bronze() -> list[Table]:
    m = meta_columns()
    people = patients()

    clinic_rows = [(c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7], *META) for c in CLINICS]

    r = fake.rng("vitalis", "dental", "patient_rows")
    patient_rows = []
    for p in people:
        a = p["address"]
        patient_rows.append((
            p["id"], p["first"], p["last"].upper() if fake.chance(r, 0.08) else p["last"], p["dob"], r.choice(RAW_GENDER[p["gender"]]),
            p["email"], p["phone"], a["address_line"], a["suburb"], a["state"], a["postcode"], r.choice(RAW_COUNTRY[p["country"]]),
            p["fund"] or None, p["fund_member_id"], p["guardian"], p["alert"] or None, p["clinic"][0], DaysAgo(p["registered"]), *META,
        ))

    r = fake.rng("vitalis", "dental", "appointments")
    staff = hr.staff_in(COMPANY, "DENTAL")
    dentists = [s for s in staff if s["title"] in ("Dentist", "Head of Dental")]
    hygienists = [s for s in staff if s["title"] == "Dental Hygienist"] or dentists
    appointments = []
    for i in range(820):
        p = r.choice(people)
        clinic = p["clinic"] if fake.chance(r, 0.9) else r.choice([c for c in CLINICS if c[6] == p["country"]])
        days_ago = r.randint(-30, 400)
        if days_ago < 0:
            status = "BOOKED"
        elif days_ago == 0:
            status = fake.weighted(r, {"COMPLETED": 50, "BOOKED": 50})
        else:
            status = fake.weighted(r, {"COMPLETED": 82, "CANCELLED": 10, "NO_SHOW": 8})
        appointment_type = fake.weighted(r, APPOINTMENT_TYPES)
        practitioner = r.choice(hygienists if appointment_type == "HYGIENE" else dentists)
        appointments.append({
            "id": f"APT{800001 + i}", "patient": p, "clinic": clinic, "days_ago": days_ago, "status": status,
            "type": appointment_type, "practitioner": practitioner["employee_id"], "minute": r.randrange(8 * 60, 17 * 60 + 30, 15),
        })
    appointment_rows = [
        (a["id"], a["patient"]["id"], a["clinic"][0], a["practitioner"], At(a["days_ago"], a["minute"]), DURATION[a["type"]],
         a["type"], r.choice((a["status"], a["status"].title(), a["status"].lower())),
         r.choice(CANCELLATION_REASONS) if a["status"] == "CANCELLED" else None,
         fake.weighted(r, {"PHONE": 70, "WALK_IN": 30}) if a["type"] == "EMERGENCY" else fake.weighted(r, {"ONLINE": 55, "PHONE": 45}),
         *META)
        for a in appointments
    ]

    r = fake.rng("vitalis", "dental", "treatments")
    treatment_rows = []
    completed = [a for a in appointments if a["status"] == "COMPLETED"]
    for a in completed:
        items = {
            "CHECK_UP": [r.choice(("011", "012", "012")), "114"] + (["022"] if fake.chance(r, 0.3) else []),
            "HYGIENE": ["114"] + (["121"] if fake.chance(r, 0.5) else []),
            "TREATMENT": [r.choice(("521", "521", "522", "522", "415", "615", "688"))] + (["022"] if fake.chance(r, 0.2) else []),
            "EMERGENCY": [r.choice(("311", "415", "521"))] + (["022"] if fake.chance(r, 0.5) else []),
            "CONSULT": ["011"] + (["022"] if fake.chance(r, 0.4) else []),
        }[a["type"]]
        tooth = r.choice(TEETH)
        a["tooth"], a["items"] = tooth, items
        fund = a["patient"]["fund"]
        for code in items:
            description, fee_range, category, tooth_specific = ITEMS[code]
            fee = fake.money(r, *fee_range)
            if fund == "Vitalis Health Insurance":
                share = {"PREVENTIVE": (0.9, 1.0), "DIAGNOSTIC": (0.8, 1.0), "GENERAL": (0.6, 0.75), "MAJOR": (0.5, 0.6)}[category]
            elif fund:
                share = (0.4, 0.6)
            else:
                share = (0.0, 0.0)
            benefit = (fee * fake.rate(r, *share)).quantize(Decimal("0.01"))
            treatment_rows.append((
                f"TRT{len(treatment_rows) + 1:06d}", a["id"], code, description, tooth if tooth_specific else None, fee, benefit,
                fee - benefit, fake.CURRENCIES[a["clinic"][6]], fund is not None and fund != "", *META,
            ))

    r = fake.rng("vitalis", "dental", "notes")
    note_rows = []
    for a in completed:
        p = a["patient"]
        if p["guardian"]:
            text = f"Child attended with guardian {p['guardian']}. Fissure sealants discussed. Reminder for the next visit sent to {p['email']}."
        elif p["alert"] == "Pregnant":
            text = f"Patient is {r.randint(8, 30)} weeks pregnant; radiographs deferred until after delivery. Gums inflamed, likely pregnancy gingivitis."
        elif a["type"] == "EMERGENCY":
            text = (f"Patient presented with severe pain and swelling on tooth {a['tooth']} for {r.randint(2, 6)} days. "
                    f"Medical history: {p['alert'] or 'nil'}. Prescribed amoxicillin. Follow-up call to {p['phone']}.")
        elif a["type"] == "TREATMENT":
            if p["alert"] == "Dental anxiety" or fake.chance(r, 0.15):
                text = f"Patient very anxious and requested nitrous oxide. {fake.name(r)[0]} {p['last']} drove them home."
            else:
                text = (f"Completed {ITEMS[a['items'][0]][0].lower()} on tooth {a['tooth']}. Patient tolerated well. "
                        f"Medical history reviewed: {p['alert'] or 'nil'}.")
        elif p["alert"] and fake.chance(r, 0.6):
            text = f"Periodic exam. Medical history updated: {p['alert']}. Bleeding gums lower front teeth; flossing reinforced. Recall 6 months."
        else:
            continue
        note_rows.append((f"DNOTE{len(note_rows) + 1:06d}", a["id"], At(a["days_ago"], a["minute"] + DURATION[a["type"]]),
                          a["practitioner"], text, *META))

    return [
        Table("bronze_clinics", "Vitalis dental clinics.", [
            Col("clinic_id", "string"), Col("clinic_name", "string"), Col("suburb", "string"), Col("city", "string"),
            Col("state", "string"), Col("postcode", "string"), Col("country", "string"), Col("dental_chairs", "int"), *m], clinic_rows),
        Table("bronze_dental_patients", "Dental patients. Children have a guardian; health_fund_member_id is a Vitalis member_id for Vitalis members.", [
            Col("patient_id", "string"), Col("first_name", "string", "Person name"), Col("last_name", "string", "Person name"),
            Col("date_of_birth", "date", "PII: date of birth"), Col("gender", "string"), Col("email", "string", "PII: email"),
            Col("mobile_phone", "string", "PII: phone number"), Col("address_line", "string", "PII: street address"),
            Col("suburb", "string"), Col("state", "string"), Col("postcode", "string"),
            Col("country", "string", "Raw country as entered: AU, AUS, Australia..."), Col("health_fund", "string"),
            Col("health_fund_member_id", "string", "Matches member_id in health_insurance for Vitalis members"),
            Col("guardian_name", "string", "Person name: parent or guardian of a child patient"),
            Col("medical_alerts", "string", "Health information: allergies, medications, pregnancy and conditions"),
            Col("home_clinic_id", "string"), Col("registered_date", "date"), *m], patient_rows),
        Table("bronze_appointments", "Appointments for the last 13 months and the next month.", [
            Col("appointment_id", "string"), Col("patient_id", "string"), Col("clinic_id", "string"),
            Col("practitioner_employee_id", "string", "Matches employee_id in the HR data"), Col("appointment_at", "timestamp"),
            Col("duration_minutes", "int"), Col("appointment_type", "string"), Col("appointment_status", "string"),
            Col("cancellation_reason", "string"), Col("booking_channel", "string"), *m], appointment_rows),
        Table("bronze_treatments", "Treatments by Australian Dental Association item number, with the health fund benefit and what the patient paid.", [
            Col("treatment_id", "string"), Col("appointment_id", "string"), Col("item_code", "string"),
            Col("item_description", "string"), Col("tooth_number", "int", "FDI tooth number"), Col("fee", "decimal(10,2)"),
            Col("fund_benefit", "decimal(10,2)"), Col("patient_paid", "decimal(10,2)"), Col("currency", "string"),
            Col("claimed_on_the_spot", "bool"), *m], treatment_rows),
        Table("bronze_dental_notes", "Clinical notes written by the practitioner after an appointment.", [
            Col("note_id", "string"), Col("appointment_id", "string"), Col("note_ts", "timestamp"),
            Col("author_employee_id", "string"),
            Col("note_text", "text", "Free text, health information: pregnancy, medications, anxiety, names and phone numbers"),
            *m], note_rows),
    ]


def silver() -> list[Derived]:
    def clinics_sql(s: Sql) -> str:
        return f"""
SELECT clinic_id, clinic_name, suburb, city, state, postcode, country, {region_sql('country')} AS region, dental_chairs
FROM {s.ref('bronze_clinics')}"""

    def patients_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH base AS (
  SELECT
    p.patient_id,
    {d.initcap('TRIM(p.first_name)')} AS first_name,
    {d.initcap('TRIM(p.last_name)')} AS last_name,
    p.date_of_birth,
    {d.age('p.date_of_birth')} AS age,
    {gender_sql('p.gender')} AS gender,
    LOWER(TRIM(p.email)) AS email,
    p.mobile_phone,
    p.address_line,
    p.suburb,
    p.state,
    p.postcode,
    {country_sql('p.country')} AS country,
    p.health_fund,
    p.health_fund_member_id,
    CASE WHEN p.health_fund = 'Vitalis Health Insurance' THEN TRUE ELSE FALSE END AS is_vitalis_member,
    p.guardian_name,
    p.medical_alerts,
    p.home_clinic_id,
    p.registered_date
  FROM {s.ref('bronze_dental_patients')} p
)
SELECT
  base.*,
  CASE WHEN base.age < 18 THEN TRUE ELSE FALSE END AS is_child,
  {age_band_sql('base.age')} AS age_band,
  {region_sql('base.country')} AS region
FROM base"""

    def appointments_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  ap.appointment_id,
  ap.patient_id,
  ap.clinic_id,
  c.clinic_name,
  ap.practitioner_employee_id,
  ap.appointment_at,
  CAST(ap.appointment_at AS DATE) AS appointment_date,
  CASE WHEN CAST(ap.appointment_at AS DATE) > {d.today} THEN TRUE ELSE FALSE END AS is_future,
  ap.duration_minutes,
  ap.appointment_type,
  UPPER(TRIM(ap.appointment_status)) AS appointment_status,
  ap.cancellation_reason,
  ap.booking_channel,
  p.age_band,
  p.country,
  p.region
FROM {s.ref('bronze_appointments')} ap
JOIN {s.ref('silver_clinics')} c ON c.clinic_id = ap.clinic_id
JOIN {s.ref('silver_dental_patients')} p ON p.patient_id = ap.patient_id"""

    def treatments_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  t.treatment_id,
  t.appointment_id,
  ap.patient_id,
  ap.clinic_id,
  ap.clinic_name,
  ap.appointment_date AS treatment_date,
  {d.month_start('ap.appointment_date')} AS treatment_month,
  t.item_code,
  t.item_description,
  CASE WHEN t.item_code IN ('011', '012', '114', '121') THEN 'PREVENTIVE' WHEN t.item_code = '022' THEN 'DIAGNOSTIC'
       WHEN t.item_code IN ('311', '521', '522') THEN 'GENERAL' ELSE 'MAJOR' END AS item_category,
  t.tooth_number,
  t.fee,
  t.fund_benefit,
  t.patient_paid,
  t.currency,
  {aud_sql('t.fee', 't.currency', d.money)} AS fee_aud,
  {aud_sql('t.fund_benefit', 't.currency', d.money)} AS fund_benefit_aud,
  {aud_sql('t.patient_paid', 't.currency', d.money)} AS patient_paid_aud,
  t.claimed_on_the_spot,
  ap.country,
  ap.region
FROM {s.ref('bronze_treatments')} t
JOIN {s.ref('silver_appointments')} ap ON ap.appointment_id = t.appointment_id"""

    def notes_sql(s: Sql) -> str:
        return f"""
SELECT n.note_id, n.appointment_id, ap.patient_id, ap.clinic_id, n.note_ts, n.author_employee_id, n.note_text, ap.country, ap.region
FROM {s.ref('bronze_dental_notes')} n
JOIN {s.ref('silver_appointments')} ap ON ap.appointment_id = n.appointment_id"""

    return [
        Derived("silver_clinics", "Clinics with region.", clinics_sql),
        Derived("silver_dental_patients", "Patients with tidied names, age, age band, child flag, gender, ISO country, region and Vitalis member flag.", patients_sql),
        Derived("silver_appointments", "Appointments with clinic, clean status, future flag and the patient's region.", appointments_sql),
        Derived("silver_treatments", "Treatments with item category, treatment date, AUD fees and benefits, and the patient's region.", treatments_sql),
        Derived("silver_dental_notes", "Dental notes with patient, clinic and region.", notes_sql),
    ]


def gold() -> list[Derived]:
    def clinic_daily_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH fees AS (
  SELECT appointment_id, SUM(fee_aud) AS fees_aud, SUM(fund_benefit_aud) AS fund_benefits_aud
  FROM {s.ref('silver_treatments')}
  GROUP BY appointment_id
)
SELECT
  ap.appointment_date,
  ap.clinic_id,
  ap.clinic_name,
  ap.region,
  COUNT(*) AS appointments,
  SUM(CASE WHEN ap.appointment_status = 'COMPLETED' THEN 1 ELSE 0 END) AS completed,
  SUM(CASE WHEN ap.appointment_status = 'BOOKED' THEN 1 ELSE 0 END) AS booked,
  SUM(CASE WHEN ap.appointment_status = 'CANCELLED' THEN 1 ELSE 0 END) AS cancelled,
  SUM(CASE WHEN ap.appointment_status = 'NO_SHOW' THEN 1 ELSE 0 END) AS no_shows,
  {d.pct("SUM(CASE WHEN ap.appointment_status = 'NO_SHOW' THEN 1 ELSE 0 END)", "SUM(CASE WHEN ap.appointment_status IN ('COMPLETED', 'NO_SHOW') THEN 1 ELSE 0 END)")} AS no_show_rate_pct,
  COALESCE(SUM(f.fees_aud), 0) AS fees_aud,
  COALESCE(SUM(f.fund_benefits_aud), 0) AS fund_benefits_aud
FROM {s.ref('silver_appointments')} ap
LEFT JOIN fees f ON f.appointment_id = ap.appointment_id
GROUP BY 1, 2, 3, 4"""

    def treatment_mix_sql(s: Sql) -> str:
        return f"""
SELECT
  treatment_month,
  item_category,
  item_code,
  item_description,
  region,
  COUNT(*) AS treatments,
  COUNT(DISTINCT patient_id) AS patients,
  SUM(fee_aud) AS fees_aud,
  SUM(fund_benefit_aud) AS fund_benefits_aud,
  SUM(patient_paid_aud) AS patient_paid_aud
FROM {s.ref('silver_treatments')}
GROUP BY 1, 2, 3, 4, 5"""

    def recall_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH visits AS (
  SELECT
    patient_id,
    MAX(CASE WHEN appointment_status = 'COMPLETED' THEN appointment_date END) AS last_visit_date,
    MAX(CASE WHEN appointment_status = 'COMPLETED' AND appointment_type IN ('CHECK_UP', 'HYGIENE') THEN appointment_date END) AS last_check_up_date,
    MIN(CASE WHEN appointment_status = 'BOOKED' AND appointment_date >= {d.today} THEN appointment_date END) AS next_appointment_date,
    SUM(CASE WHEN appointment_status = 'NO_SHOW' THEN 1 ELSE 0 END) AS no_shows
  FROM {s.ref('silver_appointments')}
  GROUP BY patient_id
)
SELECT
  p.patient_id,
  p.first_name,
  p.last_name,
  p.age,
  p.age_band,
  p.is_child,
  p.guardian_name,
  p.email,
  p.mobile_phone,
  p.health_fund,
  p.is_vitalis_member,
  p.medical_alerts,
  c.clinic_name AS home_clinic_name,
  v.last_visit_date,
  v.last_check_up_date,
  ROUND({d.days_between('v.last_check_up_date', d.today)} / 30.4, 1) AS months_since_check_up,
  v.next_appointment_date,
  COALESCE(v.no_shows, 0) AS no_shows,
  CASE WHEN v.next_appointment_date IS NULL
        AND (v.last_check_up_date IS NULL OR v.last_check_up_date < {d.add_days(d.today, -183)}) THEN TRUE ELSE FALSE END AS is_due_for_recall,
  p.country,
  p.region
FROM {s.ref('silver_dental_patients')} p
LEFT JOIN {s.ref('silver_clinics')} c ON c.clinic_id = p.home_clinic_id
LEFT JOIN visits v ON v.patient_id = p.patient_id"""

    return [
        Derived("gold_clinic_daily", "Appointments by day, clinic and patient region, including the next month's bookings: completed, cancelled, no-shows and AUD fees.", clinic_daily_sql),
        Derived("gold_treatment_mix", "Treatments by month, category, item and region, with AUD fees, fund benefits and what patients paid.", treatment_mix_sql),
        Derived("gold_patient_recall", "One row per patient: last visit and check-up, next booking, no-shows, medical alerts and whether they are due for a recall.", recall_sql),
    ]


def schema() -> Schema:
    return Schema(
        "dental",
        "Vitalis Dental",
        "Dental clinics: clinics, patients, appointments, treatments and clinical notes. "
        "Source: the practice management system (DentalPro).",
        bronze(), silver(), gold(),
    )
