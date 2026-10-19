# Vitalis Health Group

A fictional health group headquartered in Melbourne, with hospitals and
clinics across Australia and in Auckland, Wellington and Singapore. It has
three businesses: **private health insurance**, **private hospitals** and
**dental clinics**.

| File | Platform | Contains |
|---|---|---|
| [`snowflake/vitalis_health.sql`](snowflake/vitalis_health.sql) | Snowflake | Your database: schemas `health_insurance`, `hospitals`, `dental` |
| [`redshift/vitalis_hr.sql`](redshift/vitalis_hr.sql) | Redshift | Schema `vitalis` in database `hr` |
| [`bigquery/vitalis_marketing.sql`](bigquery/vitalis_marketing.sql) | BigQuery | Dataset `vitalis_marketing` |

See the [data README](../README.md) for how to run the files, the medallion
layers and regions.

## How the data connects

- `member_id` and `policy_id` link all health insurance tables. Families
  share a policy and a Medicare card.
- `insurance_member_id` in hospitals links 110 patients to their health
  insurance membership; `health_fund_member_id` in dental links 100 dental
  patients the same way. One person, three businesses.
- Vitalis' own hospitals and dental clinics are also providers in the
  claims data (`is_vitalis_owned`).
- Staff IDs in member notes (`staff_employee_id`), admissions and clinical
  notes (`attending_doctor_employee_id`, `author_employee_id`) and dental
  appointments (`practitioner_employee_id`) match `employee_id` in the HR
  data on Redshift.
- Every silver and gold table has `region` (`APAC`, `EMEA`, `AMER`) and
  `country`.

## Health insurance (`health_insurance`)

Source: the membership and claims system (MemberCore). Hospital and extras
cover in Australia and New Zealand; members in Singapore, the UK and the US
hold international (expatriate) cover.

| Bronze table | Rows | What it holds |
|---|---|---|
| `bronze_members` | 330 | Everyone on a policy: name, date of birth, contact details, **Medicare number** |
| `bronze_policies` | 153 | Gold, Silver, Bronze and Basic hospital, extras and international cover: **BSB, account and card numbers**, and the **income-based rebate tier** |
| `bronze_providers` | 40 | Hospitals, dentists, physios, optometrists, psychologists and others, including Vitalis' own |
| `bronze_claims` | 962 | 12 months of hospital and extras claims with **diagnosis codes**; 12 are duplicates |
| `bronze_member_interactions` | 260 | Contact notes: **free text with pregnancies, mental health, Medicare numbers, bank details and addresses** |

Silver cleans these up (one row per claim, ISO countries, ages and age bands,
genders, Medicare digits only, AUD amounts, gap amounts, tenure).

| Gold table | One row per |
|---|---|
| `gold_claims_monthly` | Month, claim type, service and region: claims, charges, benefits paid, gap and rejections |
| `gold_member_360` | Member: cover, claims, benefits and gap in the last 12 months, and the last contact note |
| `gold_cover_mix` | Product, membership type, rebate tier and region: active policies, members and premiums |

## Hospitals (`hospitals`)

Sources: the patient administration system (PAS) and the electronic medical
record (EMR). Ten hospitals and day surgeries; some patients are in
hospital today and some were readmitted within 28 days.

| Bronze table | Rows | What it holds |
|---|---|---|
| `bronze_hospitals` | 10 | Hospitals and day surgeries, with licensed beds |
| `bronze_patients` | 340 | Patients: contact details, **Medicare number, IHI (AU), NHI (NZ), NRIC (SG) or passport**, next of kin and GP |
| `bronze_admissions` | 475 | 12 months of admissions with **diagnosis and procedure**, payer and charges |
| `bronze_clinical_notes` | 898 | Admission, progress and discharge notes: **free text with history, allergies, mental health, next of kin and identifiers** |
| `bronze_medication_orders` | 721 | Medications ordered, with **controlled drugs** flagged |

| Gold table | One row per |
|---|---|
| `gold_daily_admissions` | Day, hospital and region: elective, emergency, maternity and same-day admissions, with charges |
| `gold_hospital_census` | Hospital: patients in hospital now, in ICU and mental health, admitted and discharged today |
| `gold_length_of_stay` | Diagnosis, ward, admission type and region: length of stay, 28 day readmissions and average charge |
| `gold_patient_journey` | Admission: patient, diagnosis, length of stay, readmission flags, medications and the latest note |

## Dental (`dental`)

Source: the practice management system (DentalPro). Twelve clinics in
Australia and New Zealand, with bookings for the next month.

| Bronze table | Rows | What it holds |
|---|---|---|
| `bronze_clinics` | 12 | Clinics, with dental chairs |
| `bronze_dental_patients` | 300 | Patients, including children with a **guardian**, health fund and **medical alerts** (allergies, anticoagulants, pregnancy) |
| `bronze_appointments` | 820 | 13 months of appointments and the next month's bookings: completed, cancelled and no-shows |
| `bronze_treatments` | 1043 | Treatments by dental item number, with fee, fund benefit and what the patient paid |
| `bronze_dental_notes` | 368 | Clinical notes: **free text with pregnancy, medical history, names and phone numbers** |

| Gold table | One row per |
|---|---|
| `gold_clinic_daily` | Day, clinic and region: bookings, completed, cancelled, no-shows and fees |
| `gold_treatment_mix` | Month, category, item and region: treatments, fees, fund benefits and patient payments |
| `gold_patient_recall` | Patient: last visit and check-up, next booking, medical alerts and whether a recall is due |

## HR (`hr.vitalis` on Redshift)

The same structure for every company (see the
[Harbourstone README](../harbourstone_financial/README.md#hr-hrharbourstone-on-redshift)).
260 employees across 11 departments, including medical staff, nursing and
dental clinics.

## Marketing (`vitalis_marketing` on BigQuery)

The same structure for every company: web sessions and events, campaigns,
ad spend, leads with **free-text messages**, email sends and consent history,
for hospital and extras cover, dental check-ups and private hospital care.

## Immuta demo ideas

- **Discovery and classification**: Medicare numbers, IHIs and NHI numbers
  (all checksum-valid), diagnosis codes, card numbers, BSBs, emails and phones
  are present, in clean columns and inside free text.
- **Masking**: hash `medicare_number` and `health_identifier`; round
  `date_of_birth` to the year; null `diagnosis_code` and
  `primary_diagnosis_code` for anyone outside clinical roles; redact phone
  numbers and Medicare numbers in `notes`, `note_text` and `latest_note` with
  a regex.
- **Row-level security**: limit every table to the user's `Region`.
  Singapore, UK and US members and patients make the effect visible.
- **Purpose and sensitivity**: restrict clinical notes, medication orders and
  mental health admissions (`ward = 'MENTAL_HEALTH'`) to treating clinicians;
  `rebate_tier` (income) to the benefits team. Children's dental records
  (`is_child`) are a good extra condition.
- **Same person, different purposes**: a member's claims are visible to the
  insurer, but their hospital notes should not be, even though
  `insurance_member_id` links them.
- **Lineage of trust**: policies on bronze columns should carry through to
  silver and gold.

## Sample questions for AI

Each question can be answered from the gold table shown.

**Health insurance**

- How much did we pay in extras benefits last month, by service, and what
  was the average gap? (`gold_claims_monthly`)
- Which members claimed the most in the last 12 months, and what was their
  last contact about? (`gold_member_360`)
- How many active policies do we have by product and membership type, and
  what is the average premium? (`gold_cover_mix`)
- What share of claims was rejected, and for which services?
  (`gold_claims_monthly`)

**Hospitals**

- How many patients are in each hospital right now, and how many are in ICU?
  (`gold_hospital_census`)
- How many emergency admissions were there in the last 30 days, by hospital?
  (`gold_daily_admissions`)
- Which diagnoses have the longest average stay and the highest 28 day
  readmission rate? (`gold_length_of_stay`)
- Summarise the current inpatients and their latest clinical notes.
  (`gold_patient_journey`)

**Dental**

- What is the no-show rate by clinic over the last three months?
  (`gold_clinic_daily`)
- How many appointments are booked for next week, by clinic?
  (`gold_clinic_daily`)
- Which treatments earn the most, and how much do patients pay out of pocket?
  (`gold_treatment_mix`)
- Which patients are due for a recall, and which of them have medical alerts?
  (`gold_patient_recall`)
