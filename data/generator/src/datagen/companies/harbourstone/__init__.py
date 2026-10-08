"""Harbourstone Financial Group: retail banking, commercial banking and
general (P&C) insurance. Head office Sydney, with branches in New Zealand,
Singapore and London. Operational data is on Databricks."""

from __future__ import annotations

from ... import hr, marketing
from ...common import Company
from ...model import Script

COMPANY = Company(
    key="harbourstone",
    name="Harbourstone Financial Group",
    folder="harbourstone_financial",
    industry="Financial Services",
    employee_id_prefix="HFG",
    email_domain="harbourstone.example.com",
    bsb_prefix="917",
    staff=240,
    departments=(
        ("EXECUTIVE", "Executive Office", (("Chief Executive Officer", "G9"), ("Executive Assistant", "G4"))),
        ("RETAIL_BANKING", "Branch Network", (("Head of Branch Network", "G8"), ("Branch Manager", "G6"),
                                               ("Customer Service Officer", "G3"), ("Personal Banker", "G4"))),
        ("RETAIL_BANKING", "Contact Centre", (("Head of Contact Centre", "G7"), ("Contact Centre Consultant", "G2"),
                                               ("Contact Centre Team Leader", "G4"))),
        ("RETAIL_BANKING", "Home Lending", (("Head of Home Lending", "G8"), ("Lending Specialist", "G5"),
                                             ("Credit Assessor", "G4"))),
        ("COMMERCIAL_BANKING", "Business Banking", (("Head of Business Banking", "G8"), ("Relationship Manager", "G6"),
                                                     ("Associate Relationship Manager", "G5"))),
        ("COMMERCIAL_BANKING", "Credit Risk", (("Chief Credit Officer", "G8"), ("Senior Credit Analyst", "G6"),
                                                ("Credit Analyst", "G5"))),
        ("INSURANCE", "Claims", (("Head of Claims", "G8"), ("Claims Officer", "G3"), ("Claims Assessor", "G4"),
                                 ("Fraud Investigator", "G5"))),
        ("INSURANCE", "Underwriting", (("Head of Underwriting", "G8"), ("Underwriter", "G5"))),
        ("RISK", "Financial Crime", (("Head of Financial Crime", "G8"), ("AML Analyst", "G5"))),
        ("TECHNOLOGY", "Data and Analytics", (("Chief Data Officer", "G8"), ("Data Engineer", "G6"), ("Data Analyst", "G5"))),
        ("CORPORATE", "People and Culture", (("Chief People Officer", "G8"), ("HR Business Partner", "G5"))),
        ("CORPORATE", "Marketing", (("Chief Marketing Officer", "G8"), ("Marketing Specialist", "G4"))),
    ),
    products=(
        ("HOME_LOANS", "Home Loans"), ("CREDIT_CARDS", "Credit Cards"), ("SAVINGS", "Savings Accounts"),
        ("BUSINESS_BANKING", "Business Banking"), ("CAR_INSURANCE", "Car Insurance"), ("HOME_INSURANCE", "Home Insurance"),
    ),
    landing_pages=(
        ("/home-loans", "HOME_LOANS"), ("/home-loans/refinance", "HOME_LOANS"), ("/credit-cards", "CREDIT_CARDS"),
        ("/savings", "SAVINGS"), ("/business", "BUSINESS_BANKING"), ("/insurance/car", "CAR_INSURANCE"),
        ("/insurance/home", "HOME_INSURANCE"),
    ),
)


def scripts() -> list[Script]:
    from . import commercial, insurance, retail

    operational = Script(
        path=f"{COMPANY.folder}/databricks/{COMPANY.folder}.sql",
        title=COMPANY.name,
        description=(
            "Retail banking, commercial banking and general insurance data for Harbourstone "
            "Financial Group, a bank and insurer headquartered in Sydney with branches in "
            "New Zealand, Singapore and London. One schema per business, each with bronze, "
            "silver and gold tables."
        ),
        platform="databricks",
        container=COMPANY.key,
        schemas=[retail.schema(), commercial.schema(), insurance.schema()],
    )
    return [operational, hr.script(COMPANY), marketing.script(COMPANY)]
