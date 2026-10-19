"""Private hospitals: hospitals, patients, admissions, clinical notes and
medication orders. About a third of patients are Vitalis health insurance
members."""

from __future__ import annotations

from decimal import Decimal

from ... import fake, hr
from ...common import aud_sql, country_sql, meta_columns, region_sql
from ...model import At, Col, Derived, Schema, Sql, Table
from . import COMPANY, HOSPITALS, RAW_COUNTRY, RAW_GENDER, age_band_sql, gender_sql, health_insurance

# (ICD-10-AM code, description, ward, procedure, admission type, length of
# stay range in days, charge range, weight). Also used for hospital claims.
DIAGNOSES = (
    ("M17.1", "Osteoarthritis of knee", "SURGICAL", "Total knee replacement", "ELECTIVE", (3, 6), (25000, 38000), 8),
    ("M16.1", "Osteoarthritis of hip", "SURGICAL", "Total hip replacement", "ELECTIVE", (3, 6), (24000, 36000), 6),
    ("K80.20", "Gallstones without cholecystitis", "SURGICAL", "Laparoscopic cholecystectomy", "ELECTIVE", (1, 2), (9000, 15000), 6),
    ("H25.9", "Age-related cataract", "DAY_SURGERY", "Cataract extraction and lens insertion", "ELECTIVE", (0, 0), (3500, 5500), 10),
    ("K21.9", "Gastro-oesophageal reflux disease", "DAY_SURGERY", "Gastroscopy", "ELECTIVE", (0, 0), (1500, 3000), 9),
    ("K63.5", "Polyp of colon", "DAY_SURGERY", "Colonoscopy and polypectomy", "ELECTIVE", (0, 0), (1800, 3500), 9),
    ("O80", "Single spontaneous delivery", "MATERNITY", "Vaginal delivery", "MATERNITY", (2, 4), (8000, 12000), 7),
    ("O82", "Delivery by caesarean section", "MATERNITY", "Caesarean section", "MATERNITY", (3, 5), (12000, 18000), 5),
    ("J18.9", "Pneumonia", "MEDICAL", "Intravenous antibiotics", "EMERGENCY", (3, 8), (7000, 16000), 6),
    ("I21.4", "Acute subendocardial myocardial infarction", "ICU", "Coronary angiography and stent", "EMERGENCY", (3, 7), (22000, 45000), 4),
    ("S72.00", "Fracture of neck of femur", "SURGICAL", "Hip hemiarthroplasty", "EMERGENCY", (5, 12), (25000, 40000), 3),
    ("N20.0", "Kidney stone", "SURGICAL", "Ureteroscopy and laser lithotripsy", "EMERGENCY", (1, 2), (6000, 10000), 4),
    ("E11.9", "Type 2 diabetes mellitus", "MEDICAL", "Diabetes stabilisation", "EMERGENCY", (2, 5), (5000, 10000), 3),
    ("C50.9", "Malignant neoplasm of breast", "SURGICAL", "Wide local excision and sentinel node biopsy", "ELECTIVE", (1, 3), (12000, 20000), 3),
    ("F32.2", "Severe depressive episode", "MENTAL_HEALTH", "Inpatient mental health care", "ELECTIVE", (10, 21), (15000, 35000), 3),
    ("F10.2", "Alcohol dependence", "MENTAL_HEALTH", "Supervised alcohol withdrawal", "ELECTIVE", (5, 10), (9000, 18000), 2),
)
PATIENT_COUNTRIES = {"AU": 80, "NZ": 9, "SG": 7, "GB": 2, "US": 2}
OTHER_INSURERS = {"Bluegum Health Fund": 35, "Southern Health Mutual": 25, "": 40}
HISTORY = ("hypertension", "type 2 diabetes", "asthma", "atrial fibrillation on apixaban", "previous stroke", "obesity",
           "obstructive sleep apnoea", "no significant history", "chronic kidney disease stage 3", "depression")
ALLERGIES = ("penicillin", "sulfur drugs", "no known allergies", "no known allergies", "codeine", "latex")
PROGRESS = {
    "SURGICAL": "Day {day} post-op. Pain {pain}/10, managed with oxycodone. Wound clean and dry. Mobilising with physio.",
    "DAY_SURGERY": "Recovered well from sedation. Tolerating fluids. Partner {nok} to drive home.",
    "MATERNITY": "Mother and baby well. Feeding established. Midwife reviewed; partner {nok} staying overnight.",
    "MEDICAL": "Afebrile overnight. Observations stable. Blood glucose {glucose} mmol/L. Tolerating oral intake.",
    "ICU": "Chest pain free. Telemetry shows sinus rhythm. Family visited; {nok} asking about the discharge date.",
    "MENTAL_HEALTH": "Attended group therapy. Sleeping better. Safety plan discussed with {nok}, who can be reached on {nok_phone}.",
}
# (medication, dose, route, frequency, controlled drug)
MEDICATIONS = {
    "SURGICAL": (("Oxycodone", "5 mg", "ORAL", "4 hourly when needed", True), ("Paracetamol", "1 g", "ORAL", "6 hourly", False),
                 ("Cefazolin", "2 g", "IV", "8 hourly", False), ("Enoxaparin", "40 mg", "SUBCUT", "daily", False)),
    "DAY_SURGERY": (("Fentanyl", "25 mcg", "IV", "once", True), ("Ondansetron", "4 mg", "IV", "when needed", False),
                    ("Paracetamol", "1 g", "ORAL", "once", False)),
    "MATERNITY": (("Ibuprofen", "400 mg", "ORAL", "8 hourly", False), ("Paracetamol", "1 g", "ORAL", "6 hourly", False),
                  ("Oxytocin", "10 units", "IM", "once", False)),
    "MEDICAL": (("Ceftriaxone", "1 g", "IV", "daily", False), ("Insulin glargine", "20 units", "SUBCUT", "nightly", False),
                ("Metformin", "500 mg", "ORAL", "twice daily", False), ("Paracetamol", "1 g", "ORAL", "6 hourly", False)),
    "ICU": (("Morphine", "2.5 mg", "IV", "2 hourly when needed", True), ("Aspirin", "100 mg", "ORAL", "daily", False),
            ("Ticagrelor", "90 mg", "ORAL", "twice daily", False), ("Heparin", "5000 units", "SUBCUT", "12 hourly", False)),
    "MENTAL_HEALTH": (("Sertraline", "50 mg", "ORAL", "daily", False), ("Diazepam", "5 mg", "ORAL", "when needed", True),
                      ("Quetiapine", "25 mg", "ORAL", "nightly", False), ("Thiamine", "100 mg", "ORAL", "daily", False)),
}
DESTINATIONS = {"HOME": 86, "REHABILITATION": 6, "TRANSFER": 5, "RESIDENTIAL_CARE": 3}
META = ("PAS", "pas-0412")

_patients: list[dict] | None = None


def patients() -> list[dict]:
    """Hospital patients. The first 110 are Vitalis health insurance members."""
    global _patients
    if _patients is not None:
        return _patients
    r = fake.rng("vitalis", "hospitals", "patients")
    adults = [m for m in health_insurance.members() if m["relationship"] != "DEPENDANT" and m["country"] in ("AU", "NZ", "SG")]
    result = []
    for i, member in enumerate(r.sample(adults, 110) + [None] * 230):
        if member:
            person = {k: member[k] for k in ("first", "last", "dob", "gender", "email", "phone", "address", "country")}
            person.update(member_id=member["id"], insurer="Vitalis Health Insurance", medicare=member["policy"]["medicare"])
        else:
            country = fake.weighted(r, PATIENT_COUNTRIES)
            first, last = fake.name(r)
            person = {"first": first, "last": last, "dob": fake.birth_date(r, 18, 92), "gender": fake.weighted(r, {"F": 52, "M": 47, "X": 1}),
                      "email": fake.email(r, first, last), "phone": fake.phone(r, country), "address": fake.address(r, country),
                      "country": country, "member_id": None, "medicare": fake.medicare_number(r) if country == "AU" else None,
                      "insurer": fake.weighted(r, OTHER_INSURERS) if country in ("AU", "NZ") else ""}
        country = person["country"]
        person["id"] = f"MRN{7000001 + i}"
        person["age"] = (fake.REFERENCE_DATE - person["dob"]).days // 365
        person["identifier"], person["identifier_type"] = {
            "AU": (fake.ihi(r), "IHI"), "NZ": (fake.nhi(r), "NHI"),
            "SG": (f"S{fake.digits(r, 7)}{r.choice('ABCDEFGHIZJ')}", "NRIC"),
        }.get(country, (fake.passport(r, country), "PASSPORT"))
        nok_first, nok_last = fake.name(r)
        person["nok"] = f"{nok_first} {person['last'] if fake.chance(r, 0.6) else nok_last}"
        person["nok_phone"] = fake.phone(r, country)
        gp_first, gp_last = fake.name(r)
        person["gp"] = f"Dr {gp_first[0]} {gp_last}"
        result.append(person)
    _patients = result
    return result


def bronze() -> list[Table]:
    m = meta_columns()
    people = patients()

    hospital_rows = [(h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7], *META) for h in HOSPITALS]

    r = fake.rng("vitalis", "hospitals", "patient_rows")
    patient_rows = []
    for p in people:
        a = p["address"]
        patient_rows.append((
            p["id"], p["first"].upper() if fake.chance(r, 0.1) else p["first"], p["last"].upper() if fake.chance(r, 0.1) else p["last"],
            p["dob"], r.choice(RAW_GENDER[p["gender"]]), p["email"], p["phone"], a["address_line"], a["suburb"], a["state"],
            a["postcode"], r.choice(RAW_COUNTRY[p["country"]]), p["medicare"], p["identifier"], p["identifier_type"],
            p["insurer"] or None, p["member_id"], p["nok"], p["nok_phone"], p["gp"], *META,
        ))

    r = fake.rng("vitalis", "hospitals", "admissions")
    staff = hr.staff_in(COMPANY, "HOSPITALS")
    doctors = [s for s in staff if s["department"]["department_name"] == "Medical Staff"]
    nurses = [s for s in staff if s["department"]["department_name"] == "Nursing"]
    pharmacists = [s for s in staff if s["title"] == "Pharmacist"] or nurses
    admissions = []

    def admit(p, hospital, diagnosis, admitted, admission_type):
        los = r.randint(*diagnosis[5])
        discharged = admitted - los
        if discharged < 0 or (admitted == 0 and fake.chance(r, 0.4)):
            discharged = None  # still in hospital
        if p["member_id"] or p["insurer"]:
            payer = "PRIVATE_INSURANCE"
        elif p["country"] in ("GB", "US"):
            payer = "INTERNATIONAL"
        else:
            payer = fake.weighted(r, {"SELF_FUNDED": 60, "DVA": 20, "WORKERS_COMPENSATION": 20})
        currency = fake.CURRENCIES[hospital[6]]
        charge = fake.money(r, *diagnosis[6]) * (Decimal("1.0") + Decimal("0.04") * max(los - diagnosis[5][0], 0))
        admissions.append({
            "id": f"ADM{900001 + len(admissions)}", "patient": p, "hospital": hospital, "diagnosis": diagnosis, "los": los,
            "admitted": admitted, "discharged": discharged, "type": admission_type, "payer": payer, "currency": currency,
            "charge": charge.quantize(Decimal("0.01")), "doctor": r.choice(doctors)["employee_id"],
            "admit_minute": fake.minute_of_day(r, 7, 11) if admission_type == "ELECTIVE" else fake.minute_of_day(r, 0, 24),
            "destination": fake.weighted(r, DESTINATIONS) if los > 2 and diagnosis[2] in ("SURGICAL", "MEDICAL", "ICU") else "HOME",
        })

    for i in range(450):
        p = people[i] if i < len(people) else r.choice(people)
        local = [h for h in HOSPITALS if h[6] == p["country"]] or [h for h in HOSPITALS if h[6] == "AU"]
        hospital = r.choice(local)
        options = [d for d in DIAGNOSES if hospital[7] >= 40 or d[2] == "DAY_SURGERY"]
        if p["gender"] != "F" or not 18 <= p["age"] <= 45:
            options = [d for d in options if d[2] != "MATERNITY"]
        diagnosis = r.choices(options, weights=[d[7] for d in options])[0]
        admit(p, hospital, diagnosis, 0 if fake.chance(r, 0.03) else r.randint(1, 365), diagnosis[4])
    # Unplanned readmissions within 28 days of discharge, for the same problem.
    for a in r.sample([a for a in admissions if a["discharged"] and a["discharged"] > 5 and a["los"] > 0], 25):
        admit(a["patient"], a["hospital"], a["diagnosis"], a["discharged"] - r.randint(2, min(27, a["discharged"])), "EMERGENCY")
    admission_rows = [
        (a["id"], a["patient"]["id"], a["hospital"][0], At(a["admitted"], a["admit_minute"]),
         At(a["discharged"], fake.minute_of_day(r, 9, 15)) if a["discharged"] is not None else None,
         r.choice((a["type"], a["type"].title())), a["diagnosis"][2], a["diagnosis"][0], a["diagnosis"][1], a["diagnosis"][3],
         a["doctor"], a["payer"], a["patient"]["insurer"] or None, a["charge"], a["currency"],
         a["destination"] if a["discharged"] is not None else None, *META)
        for a in admissions
    ]

    r = fake.rng("vitalis", "hospitals", "notes")
    note_rows = []

    def note(a, days_ago, minute, role, author, note_type, text):
        note_rows.append((f"NOTE{len(note_rows) + 1:06d}", a["id"], At(days_ago, minute), role, author, note_type, text, "EMR", "emr-0412"))

    for a in admissions:
        p, d = a["patient"], a["diagnosis"]
        sex = {"F": "woman", "M": "man"}.get(p["gender"], "person")
        note(a, a["admitted"], min(a["admit_minute"] + 30, 1439), "DOCTOR", a["doctor"], "ADMISSION",
             f"{p['age']} year old {sex} admitted ({a['type'].lower()}) for {d[3].lower()}: {d[1].lower()}. "
             f"History: {r.choice(HISTORY)}. Allergies: {r.choice(ALLERGIES)}. Next of kin {p['nok']} on {p['nok_phone']}.")
        if a["los"] > 0 and fake.chance(r, 0.35):
            day = r.randint(1, a["los"])
            if a["admitted"] - day >= 0:
                note(a, a["admitted"] - day, fake.minute_of_day(r, 6, 22), "NURSE", r.choice(nurses)["employee_id"], "PROGRESS",
                     PROGRESS[d[2]].format(day=day, pain=r.randint(1, 6), nok=p["nok"], nok_phone=p["nok_phone"],
                                           glucose=r.randint(5, 14)))
        if a["discharged"] is not None and (a["los"] > 0 or fake.chance(r, 0.4)):
            identifier = f"Medicare {p['medicare']}" if p["medicare"] else f"{p['identifier_type']} {p['identifier']}"
            note(a, a["discharged"], fake.minute_of_day(r, 9, 15), "DOCTOR", a["doctor"], "DISCHARGE_SUMMARY",
                 f"Discharged to {a['destination'].lower().replace('_', ' ')} after {a['los']} night{'' if a['los'] == 1 else 's'}. "
                 f"Procedure: {d[3].lower()}. Diagnosis: {d[1].lower()} ({d[0]}). "
                 f"GP {p['gp']} to review in two weeks. {identifier}.")

    r = fake.rng("vitalis", "hospitals", "medications")
    medication_rows = []
    for a in admissions:
        for drug, dose, route, frequency, controlled in r.sample(MEDICATIONS[a["diagnosis"][2]], r.randint(1, 2)):
            medication_rows.append((f"MED{len(medication_rows) + 1:06d}", a["id"], At(a["admitted"], min(a["admit_minute"] + r.randint(30, 240), 1439)),
                                    drug, dose, route, frequency, controlled, a["doctor"],
                                    r.choice(pharmacists)["employee_id"], "EMR", "emr-0412"))

    return [
        Table("bronze_hospitals", "Vitalis private hospitals and day surgeries.", [
            Col("hospital_id", "string"), Col("hospital_name", "string"), Col("suburb", "string"), Col("city", "string"),
            Col("state", "string"), Col("postcode", "string"), Col("country", "string"), Col("licensed_beds", "int"), *m], hospital_rows),
        Table("bronze_patients", "Patients from the patient administration system. insurance_member_id links patients who are Vitalis health insurance members.", [
            Col("patient_id", "string", "Medical record number"), Col("first_name", "string", "Person name"),
            Col("last_name", "string", "Person name"), Col("date_of_birth", "date", "PII: date of birth"), Col("gender", "string"),
            Col("email", "string", "PII: email"), Col("mobile_phone", "string", "PII: phone number"),
            Col("address_line", "string", "PII: street address"), Col("suburb", "string"), Col("state", "string"),
            Col("postcode", "string"), Col("country", "string", "Raw country as entered: AU, AUS, Australia..."),
            Col("medicare_number", "string", "Highly sensitive: Medicare card number"),
            Col("health_identifier", "string", "Highly sensitive: IHI (AU), NHI (NZ), NRIC (SG) or passport number"),
            Col("health_identifier_type", "string"), Col("insurer_name", "string"),
            Col("insurance_member_id", "string", "Matches member_id in health_insurance"),
            Col("next_of_kin_name", "string", "Person name"), Col("next_of_kin_phone", "string", "PII: phone number"),
            Col("gp_name", "string", "Person name: the patient's general practitioner"), *m], patient_rows),
        Table("bronze_admissions", "Hospital admissions for the last 12 months. discharged_at is empty for patients still in hospital.", [
            Col("admission_id", "string"), Col("patient_id", "string"), Col("hospital_id", "string"), Col("admitted_at", "timestamp"),
            Col("discharged_at", "timestamp"), Col("admission_type", "string"), Col("ward", "string"),
            Col("primary_diagnosis_code", "string", "Health information: ICD-10-AM diagnosis code"),
            Col("diagnosis_description", "string", "Health information"), Col("procedure_description", "string", "Health information"),
            Col("attending_doctor_employee_id", "string", "Matches employee_id in the HR data"), Col("payer_type", "string"),
            Col("insurer_name", "string"), Col("total_charge", "decimal(12,2)"), Col("currency", "string"),
            Col("discharge_destination", "string"), *m], admission_rows),
        Table("bronze_clinical_notes", "Admission, progress and discharge notes from the electronic medical record.", [
            Col("note_id", "string"), Col("admission_id", "string"), Col("note_ts", "timestamp"), Col("author_role", "string"),
            Col("author_employee_id", "string"), Col("note_type", "string"),
            Col("note_text", "text", "Free text, health information: diagnoses, history, allergies, next of kin, phone numbers and Medicare numbers"),
            *m], note_rows),
        Table("bronze_medication_orders", "Medications ordered for admitted patients. Controlled drugs (Schedule 8) are flagged.", [
            Col("order_id", "string"), Col("admission_id", "string"), Col("ordered_at", "timestamp"), Col("medication", "string"),
            Col("dose", "string"), Col("route", "string"), Col("frequency", "string"), Col("is_controlled_drug", "bool"),
            Col("prescriber_employee_id", "string"), Col("pharmacist_employee_id", "string"), *m], medication_rows),
    ]


def silver() -> list[Derived]:
    def hospitals_sql(s: Sql) -> str:
        return f"""
SELECT hospital_id, hospital_name, suburb, city, state, postcode, country, {region_sql('country')} AS region, licensed_beds
FROM {s.ref('bronze_hospitals')}"""

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
    REGEXP_REPLACE(p.medicare_number, '[^0-9]', '') AS medicare_number,
    REGEXP_REPLACE(p.health_identifier, ' ', '') AS health_identifier,
    p.health_identifier_type,
    p.insurer_name,
    p.insurance_member_id,
    CASE WHEN p.insurance_member_id IS NULL THEN FALSE ELSE TRUE END AS is_vitalis_member,
    p.next_of_kin_name,
    p.next_of_kin_phone,
    p.gp_name
  FROM {s.ref('bronze_patients')} p
)
SELECT
  base.*,
  {age_band_sql('base.age')} AS age_band,
  {region_sql('base.country')} AS region
FROM base"""

    def admissions_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH base AS (
  SELECT
    a.*,
    CAST(a.admitted_at AS DATE) AS admit_date,
    CAST(a.discharged_at AS DATE) AS discharge_date,
    LAG(a.discharged_at) OVER (PARTITION BY a.patient_id ORDER BY a.admitted_at) AS previous_discharged_at,
    LEAD(a.admitted_at) OVER (PARTITION BY a.patient_id ORDER BY a.admitted_at) AS next_admitted_at
  FROM {s.ref('bronze_admissions')} a
)
SELECT
  a.admission_id,
  a.patient_id,
  a.hospital_id,
  h.hospital_name,
  a.admitted_at,
  a.admit_date,
  {d.month_start('a.admit_date')} AS admit_month,
  a.discharged_at,
  a.discharge_date,
  CASE WHEN a.discharged_at IS NULL THEN TRUE ELSE FALSE END AS is_current_inpatient,
  {d.days_between('a.admit_date', f'COALESCE(a.discharge_date, {d.today})')} AS length_of_stay_days,
  CASE WHEN a.discharge_date = a.admit_date THEN TRUE ELSE FALSE END AS is_same_day,
  UPPER(TRIM(a.admission_type)) AS admission_type,
  a.ward,
  a.primary_diagnosis_code,
  a.diagnosis_description,
  a.procedure_description,
  CASE WHEN a.previous_discharged_at IS NOT NULL
        AND {d.days_between('a.previous_discharged_at', 'a.admitted_at')} <= 28 THEN TRUE ELSE FALSE END AS is_readmission_28_days,
  CASE WHEN a.discharged_at IS NOT NULL AND a.next_admitted_at IS NOT NULL
        AND {d.days_between('a.discharged_at', 'a.next_admitted_at')} <= 28 THEN TRUE ELSE FALSE END AS readmitted_within_28_days,
  a.attending_doctor_employee_id,
  a.payer_type,
  a.insurer_name,
  a.total_charge,
  a.currency,
  {aud_sql('a.total_charge', 'a.currency', d.money)} AS total_charge_aud,
  a.discharge_destination,
  p.age_band,
  p.gender,
  p.country,
  p.region
FROM base a
JOIN {s.ref('silver_hospitals')} h ON h.hospital_id = a.hospital_id
JOIN {s.ref('silver_patients')} p ON p.patient_id = a.patient_id"""

    def notes_sql(s: Sql) -> str:
        return f"""
SELECT n.note_id, n.admission_id, a.patient_id, a.hospital_id, a.ward, n.note_ts, n.author_role, n.author_employee_id,
       n.note_type, n.note_text, a.country, a.region
FROM {s.ref('bronze_clinical_notes')} n
JOIN {s.ref('silver_admissions')} a ON a.admission_id = n.admission_id"""

    def medications_sql(s: Sql) -> str:
        return f"""
SELECT mo.order_id, mo.admission_id, a.patient_id, a.hospital_id, a.ward, mo.ordered_at, mo.medication, mo.dose, mo.route,
       mo.frequency, mo.is_controlled_drug, mo.prescriber_employee_id, mo.pharmacist_employee_id, a.country, a.region
FROM {s.ref('bronze_medication_orders')} mo
JOIN {s.ref('silver_admissions')} a ON a.admission_id = mo.admission_id"""

    return [
        Derived("silver_hospitals", "Hospitals with region.", hospitals_sql),
        Derived("silver_patients", "Patients with tidied names, age and age band, gender, ISO country, region and identifiers without spaces.", patients_sql),
        Derived("silver_admissions", "Admissions with length of stay, current inpatient and 28 day readmission flags, AUD charges and the patient's region.", admissions_sql),
        Derived("silver_clinical_notes", "Clinical notes with the patient, hospital, ward and region.", notes_sql),
        Derived("silver_medication_orders", "Medication orders with the patient, hospital, ward and region.", medications_sql),
    ]


def gold() -> list[Derived]:
    def daily_sql(s: Sql) -> str:
        return f"""
SELECT
  admit_date,
  hospital_id,
  hospital_name,
  region,
  COUNT(*) AS admissions,
  SUM(CASE WHEN admission_type = 'ELECTIVE' THEN 1 ELSE 0 END) AS elective_admissions,
  SUM(CASE WHEN admission_type = 'EMERGENCY' THEN 1 ELSE 0 END) AS emergency_admissions,
  SUM(CASE WHEN admission_type = 'MATERNITY' THEN 1 ELSE 0 END) AS maternity_admissions,
  SUM(CASE WHEN is_same_day THEN 1 ELSE 0 END) AS same_day_admissions,
  SUM(total_charge_aud) AS total_charges_aud
FROM {s.ref('silver_admissions')}
GROUP BY 1, 2, 3, 4"""

    def census_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH inpatients AS (
  SELECT hospital_id, COUNT(*) AS current_inpatients,
         SUM(CASE WHEN ward = 'ICU' THEN 1 ELSE 0 END) AS icu_patients,
         SUM(CASE WHEN ward = 'MENTAL_HEALTH' THEN 1 ELSE 0 END) AS mental_health_patients
  FROM {s.ref('silver_admissions')}
  WHERE is_current_inpatient
  GROUP BY hospital_id
),
admitted AS (
  SELECT hospital_id, COUNT(*) AS admitted_today FROM {s.ref('silver_admissions')} WHERE admit_date = {d.today} GROUP BY hospital_id
),
discharged AS (
  SELECT hospital_id, COUNT(*) AS discharged_today FROM {s.ref('silver_admissions')} WHERE discharge_date = {d.today} GROUP BY hospital_id
)
SELECT
  h.hospital_id,
  h.hospital_name,
  h.city,
  h.state,
  h.country,
  h.region,
  h.licensed_beds,
  COALESCE(i.current_inpatients, 0) AS current_inpatients,
  COALESCE(i.icu_patients, 0) AS icu_patients,
  COALESCE(i.mental_health_patients, 0) AS mental_health_patients,
  COALESCE(ad.admitted_today, 0) AS admitted_today,
  COALESCE(di.discharged_today, 0) AS discharged_today
FROM {s.ref('silver_hospitals')} h
LEFT JOIN inpatients i ON i.hospital_id = h.hospital_id
LEFT JOIN admitted ad ON ad.hospital_id = h.hospital_id
LEFT JOIN discharged di ON di.hospital_id = h.hospital_id"""

    def length_of_stay_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  primary_diagnosis_code,
  diagnosis_description,
  ward,
  admission_type,
  region,
  COUNT(*) AS discharges_12_months,
  ROUND(AVG(length_of_stay_days), 1) AS avg_length_of_stay_days,
  MAX(length_of_stay_days) AS max_length_of_stay_days,
  SUM(CASE WHEN readmitted_within_28_days THEN 1 ELSE 0 END) AS readmissions_28_days,
  {d.pct('SUM(CASE WHEN readmitted_within_28_days THEN 1 ELSE 0 END)', 'COUNT(*)')} AS readmission_rate_pct,
  {d.money('AVG(total_charge_aud)')} AS avg_charge_aud
FROM {s.ref('silver_admissions')}
WHERE NOT is_current_inpatient AND admit_date >= {d.add_days(d.today, -365)}
GROUP BY 1, 2, 3, 4, 5"""

    def journey_sql(s: Sql) -> str:
        return f"""
WITH latest_note AS (
  SELECT admission_id, note_type, note_text, ROW_NUMBER() OVER (PARTITION BY admission_id ORDER BY note_ts DESC) AS rn
  FROM {s.ref('silver_clinical_notes')}
),
medications AS (
  SELECT admission_id, COUNT(*) AS medications_ordered,
         SUM(CASE WHEN is_controlled_drug THEN 1 ELSE 0 END) AS controlled_drugs_ordered
  FROM {s.ref('silver_medication_orders')}
  GROUP BY admission_id
)
SELECT
  a.admission_id,
  a.patient_id,
  p.first_name,
  p.last_name,
  p.age,
  p.age_band,
  p.gender,
  p.is_vitalis_member,
  a.hospital_name,
  a.admit_date,
  a.discharge_date,
  a.is_current_inpatient,
  a.length_of_stay_days,
  a.admission_type,
  a.ward,
  a.primary_diagnosis_code,
  a.diagnosis_description,
  a.procedure_description,
  a.is_readmission_28_days,
  a.readmitted_within_28_days,
  a.payer_type,
  a.total_charge_aud,
  COALESCE(mo.medications_ordered, 0) AS medications_ordered,
  COALESCE(mo.controlled_drugs_ordered, 0) AS controlled_drugs_ordered,
  n.note_type AS latest_note_type,
  n.note_text AS latest_note,
  a.country,
  a.region
FROM {s.ref('silver_admissions')} a
JOIN {s.ref('silver_patients')} p ON p.patient_id = a.patient_id
LEFT JOIN medications mo ON mo.admission_id = a.admission_id
LEFT JOIN latest_note n ON n.admission_id = a.admission_id AND n.rn = 1"""

    return [
        Derived("gold_daily_admissions", "Admissions by day, hospital and patient region: elective, emergency, maternity and same-day, with AUD charges.", daily_sql),
        Derived("gold_hospital_census", "One row per hospital: patients in hospital now, in ICU and mental health wards, and admitted and discharged today.", census_sql),
        Derived("gold_length_of_stay", "Discharges in the last 12 months by diagnosis, ward, admission type and region: length of stay, 28 day readmissions and average charge.", length_of_stay_sql),
        Derived("gold_patient_journey", "One row per admission: patient, hospital, diagnosis, length of stay, readmission flags, medications and the latest clinical note.", journey_sql),
    ]


def schema() -> Schema:
    return Schema(
        "hospitals",
        "Vitalis Hospitals",
        "Private hospitals: hospitals, patients, admissions, clinical notes and medication orders. "
        "Sources: the patient administration system (PAS) and the electronic medical record (EMR).",
        bronze(), silver(), gold(),
    )
