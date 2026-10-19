"""Vitalis Health Group: private health insurance, private hospitals and
dental clinics. Head office Melbourne, with hospitals and clinics in New
Zealand and Singapore. Operational data is on Snowflake."""

from __future__ import annotations

from ... import hr, marketing
from ...common import Company
from ...model import Script

COMPANY = Company(
    key="vitalis",
    name="Vitalis Health Group",
    folder="vitalis_health",
    industry="Health",
    employee_id_prefix="VHG",
    email_domain="vitalis.example.com",
    bsb_prefix="926",
    staff=260,
    departments=(
        ("EXECUTIVE", "Executive Office", (("Chief Executive Officer", "G9"), ("Executive Assistant", "G4"))),
        ("HEALTH_INSURANCE", "Member Services", (("Head of Member Services", "G8"), ("Member Services Consultant", "G2"),
                                                 ("Member Services Team Leader", "G4"))),
        ("HEALTH_INSURANCE", "Benefits and Claims", (("Head of Benefits", "G8"), ("Claims Assessor", "G3"),
                                                     ("Benefits Analyst", "G5"))),
        ("HOSPITALS", "Medical Staff", (("Chief Medical Officer", "G9"), ("Consultant Physician", "G8"), ("Surgeon", "G9"),
                                        ("Registrar", "G6"))),
        ("HOSPITALS", "Nursing", (("Director of Nursing", "G8"), ("Registered Nurse", "G4"), ("Clinical Nurse Specialist", "G5"),
                                  ("Enrolled Nurse", "G3"))),
        ("HOSPITALS", "Allied Health", (("Head of Allied Health", "G7"), ("Physiotherapist", "G4"), ("Pharmacist", "G5"))),
        ("DENTAL", "Dental Clinics", (("Head of Dental", "G8"), ("Dentist", "G6"), ("Dental Hygienist", "G4"),
                                      ("Dental Assistant", "G2"))),
        ("RISK", "Clinical Governance", (("Head of Clinical Governance", "G8"), ("Patient Safety Officer", "G5"))),
        ("TECHNOLOGY", "Data and Analytics", (("Chief Data Officer", "G8"), ("Data Engineer", "G6"), ("Data Analyst", "G5"))),
        ("CORPORATE", "People and Culture", (("Chief People Officer", "G8"), ("HR Business Partner", "G5"))),
        ("CORPORATE", "Marketing", (("Chief Marketing Officer", "G8"), ("Marketing Specialist", "G4"))),
    ),
    products=(
        ("HOSPITAL_COVER", "Hospital Cover"), ("EXTRAS_COVER", "Extras Cover"), ("INTERNATIONAL_COVER", "International Health Cover"),
        ("DENTAL_CHECKUP", "Dental Check-ups"), ("PRIVATE_HOSPITAL", "Private Hospital Care"), ("TELEHEALTH", "Telehealth"),
    ),
    landing_pages=(
        ("/health-insurance/hospital", "HOSPITAL_COVER"), ("/health-insurance/extras", "EXTRAS_COVER"),
        ("/health-insurance/international", "INTERNATIONAL_COVER"), ("/dental/book", "DENTAL_CHECKUP"),
        ("/hospitals", "PRIVATE_HOSPITAL"), ("/hospitals/maternity", "PRIVATE_HOSPITAL"), ("/telehealth", "TELEHEALTH"),
    ),
)

# Vitalis' own hospitals and dental clinics. They are also providers in the
# health insurance data, so claims at them can be told apart.
# (id, name, suburb, city, state, postcode, country, beds or chairs)
HOSPITALS = (
    ("H01", "Vitalis Private Hospital Melbourne", "Melbourne", "Melbourne", "VIC", "3000", "AU", 220),
    ("H02", "Vitalis Richmond Day Surgery", "Richmond", "Melbourne", "VIC", "3121", "AU", 30),
    ("H03", "Vitalis Geelong Private", "Geelong", "Geelong", "VIC", "3220", "AU", 90),
    ("H04", "Vitalis Private Hospital Sydney", "Chatswood", "Sydney", "NSW", "2067", "AU", 180),
    ("H05", "Vitalis Brisbane Private", "Brisbane", "Brisbane", "QLD", "4000", "AU", 150),
    ("H06", "Vitalis Gold Coast Day Hospital", "Southport", "Gold Coast", "QLD", "4215", "AU", 24),
    ("H07", "Vitalis Perth Private", "Joondalup", "Perth", "WA", "6027", "AU", 120),
    ("H08", "Vitalis Adelaide Private", "Adelaide", "Adelaide", "SA", "5000", "AU", 100),
    ("H09", "Vitalis Auckland Surgical Centre", "Takapuna", "Auckland", "AUK", "0622", "NZ", 60),
    ("H10", "Vitalis Singapore Medical Centre", "Bukit Timah", "Singapore", "SG", "259760", "SG", 80),
)
CLINICS = (
    ("DC01", "Vitalis Dental Melbourne CBD", "Melbourne", "Melbourne", "VIC", "3000", "AU", 8),
    ("DC02", "Vitalis Dental Carlton", "Carlton", "Melbourne", "VIC", "3053", "AU", 4),
    ("DC03", "Vitalis Dental Richmond", "Richmond", "Melbourne", "VIC", "3121", "AU", 5),
    ("DC04", "Vitalis Dental Geelong", "Geelong", "Geelong", "VIC", "3220", "AU", 4),
    ("DC05", "Vitalis Dental Ballarat", "Ballarat", "Ballarat", "VIC", "3350", "AU", 3),
    ("DC06", "Vitalis Dental Sydney CBD", "Sydney", "Sydney", "NSW", "2000", "AU", 7),
    ("DC07", "Vitalis Dental Bondi", "Bondi", "Sydney", "NSW", "2026", "AU", 4),
    ("DC08", "Vitalis Dental Parramatta", "Parramatta", "Sydney", "NSW", "2150", "AU", 5),
    ("DC09", "Vitalis Dental Brisbane", "Brisbane", "Brisbane", "QLD", "4000", "AU", 5),
    ("DC10", "Vitalis Dental Hobart", "Hobart", "Hobart", "TAS", "7000", "AU", 3),
    ("DC11", "Vitalis Dental Ponsonby", "Ponsonby", "Auckland", "AUK", "1011", "NZ", 4),
    ("DC12", "Vitalis Dental Te Aro", "Te Aro", "Wellington", "WGN", "6011", "NZ", 3),
)
# How source systems spell each country; silver cleans these up.
RAW_COUNTRY = {"AU": ("AU", "AU", "AU", "Australia", "AUS", "au "), "NZ": ("NZ", "New Zealand", "NZL"), "SG": ("SG", "Singapore"),
               "GB": ("GB", "UK"), "US": ("US", "USA")}
RAW_GENDER = {"F": ("F", "Female", "female"), "M": ("M", "Male", "male"), "X": ("X", "Non-binary")}


def gender_sql(column: str) -> str:
    """F, M or X from the spellings in RAW_GENDER."""
    cleaned = f"UPPER(TRIM({column}))"
    return f"CASE WHEN {cleaned} IN ('F', 'FEMALE') THEN 'F' WHEN {cleaned} IN ('M', 'MALE') THEN 'M' ELSE 'X' END"


def age_band_sql(age: str) -> str:
    return (f"CASE WHEN {age} < 18 THEN '0-17' WHEN {age} < 25 THEN '18-24' WHEN {age} < 35 THEN '25-34' "
            f"WHEN {age} < 50 THEN '35-49' WHEN {age} < 65 THEN '50-64' ELSE '65+' END")


def scripts() -> list[Script]:
    from . import dental, health_insurance, hospitals

    operational = Script(
        path=f"{COMPANY.folder}/snowflake/{COMPANY.folder}.sql",
        title=COMPANY.name,
        description=(
            "Private health insurance, private hospital and dental clinic data for Vitalis Health "
            "Group, headquartered in Melbourne with hospitals and clinics in New Zealand and "
            "Singapore. One schema per business, each with bronze, silver and gold tables."
        ),
        platform="snowflake",
        container=COMPANY.key,
        schemas=[health_insurance.schema(), hospitals.schema(), dental.schema()],
    )
    return [operational, hr.script(COMPANY), marketing.script(COMPANY)]
