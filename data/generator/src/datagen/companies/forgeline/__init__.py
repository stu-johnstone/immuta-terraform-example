"""Forgeline Industries: makes industrial pumps, valves, conveyors and custom
fabrication. Head office Adelaide, with plants in Australia, New Zealand and
the US. Operational data is on Snowflake."""

from __future__ import annotations

from decimal import Decimal

from ... import hr, marketing
from ...common import Company
from ...model import Script

COMPANY = Company(
    key="forgeline",
    name="Forgeline Industries",
    folder="forgeline_industries",
    industry="Manufacturing",
    employee_id_prefix="FGI",
    email_domain="forgeline.example.com",
    bsb_prefix="934",
    staff=230,
    departments=(
        ("EXECUTIVE", "Executive Office", (("Chief Executive Officer", "G9"), ("Executive Assistant", "G4"))),
        ("PRODUCTION", "Plant Operations", (("General Manager Operations", "G8"), ("Production Supervisor", "G5"),
                                            ("Machine Operator", "G2"), ("Fitter and Turner", "G3"), ("Welder", "G3"))),
        ("PRODUCTION", "Maintenance", (("Head of Maintenance", "G7"), ("Maintenance Technician", "G4"), ("Electrician", "G4"))),
        ("PRODUCTION", "Health and Safety", (("Head of Health and Safety", "G7"), ("Safety Advisor", "G5"))),
        ("SUPPLY_CHAIN", "Procurement", (("Head of Procurement", "G8"), ("Buyer", "G4"), ("Category Manager", "G6"))),
        ("SUPPLY_CHAIN", "Logistics", (("Head of Logistics", "G7"), ("Warehouse Operator", "G2"), ("Logistics Coordinator", "G3"))),
        ("SUPPLY_CHAIN", "Sales", (("Head of Sales", "G8"), ("Account Manager", "G5"), ("Sales Coordinator", "G3"))),
        ("QUALITY", "Quality Assurance", (("Head of Quality", "G8"), ("Quality Inspector", "G3"), ("Quality Engineer", "G5"))),
        ("TECHNOLOGY", "Data and Analytics", (("Chief Data Officer", "G8"), ("Data Engineer", "G6"), ("Data Analyst", "G5"))),
        ("CORPORATE", "Finance", (("Chief Financial Officer", "G9"), ("Accountant", "G5"))),
        ("CORPORATE", "People and Culture", (("Chief People Officer", "G8"), ("HR Business Partner", "G5"))),
        ("CORPORATE", "Marketing", (("Chief Marketing Officer", "G8"), ("Marketing Specialist", "G4"))),
    ),
    products=(
        ("PUMPS", "Industrial Pumps"), ("VALVES", "Valves and Actuators"), ("CONVEYORS", "Conveyor Systems"),
        ("FABRICATION", "Custom Fabrication"), ("SPARE_PARTS", "Spare Parts"), ("FIELD_SERVICE", "Field Service"),
    ),
    landing_pages=(
        ("/products/pumps", "PUMPS"), ("/products/valves", "VALVES"), ("/products/conveyors", "CONVEYORS"),
        ("/fabrication", "FABRICATION"), ("/parts", "SPARE_PARTS"), ("/service", "FIELD_SERVICE"), ("/request-a-quote", "PUMPS"),
    ),
)

# (site id, name, type, suburb, city, state, postcode, country)
SITES = (
    ("S01", "Adelaide Pump Works", "PLANT", "Wingfield", "Adelaide", "SA", "5013", "AU"),
    ("S02", "Geelong Valve Plant", "PLANT", "North Geelong", "Geelong", "VIC", "3215", "AU"),
    ("S03", "Brisbane Conveyor Plant", "PLANT", "Eagle Farm", "Brisbane", "QLD", "4009", "AU"),
    ("S04", "Auckland Fabrication Plant", "PLANT", "East Tamaki", "Auckland", "AUK", "2013", "NZ"),
    ("S05", "Austin Assembly Plant", "PLANT", "Del Valle", "Austin", "TX", "78617", "US"),
    ("S06", "Sydney Distribution Centre", "WAREHOUSE", "Wetherill Park", "Sydney", "NSW", "2164", "AU"),
    ("S07", "Perth Distribution Centre", "WAREHOUSE", "Kewdale", "Perth", "WA", "6105", "AU"),
    ("S08", "Singapore Regional Warehouse", "WAREHOUSE", "Tuas", "Singapore", "SG", "638367", "SG"),
    ("S09", "Melbourne Service Centre", "SERVICE_CENTRE", "Dandenong South", "Melbourne", "VIC", "3175", "AU"),
    ("S10", "Townsville Service Centre", "SERVICE_CENTRE", "Bohle", "Townsville", "QLD", "4818", "AU"),
    ("S11", "Manchester Service Centre", "SERVICE_CENTRE", "Trafford Park", "Manchester", "MAN", "M17 1AA", "GB"),
)
SITE = {s[0]: s for s in SITES}
# (line id, site id, name, product family, rated units per hour, shift pattern)
LINES = (
    ("L01", "S01", "Pump Line 1", "PUMPS", Decimal("6.0"), "3x8"),
    ("L02", "S01", "Pump Line 2", "PUMPS", Decimal("5.0"), "3x8"),
    ("L03", "S01", "Pump Parts Cell", "SPARE_PARTS", Decimal("20.0"), "2x8"),
    ("L04", "S02", "Valve Line 1", "VALVES", Decimal("12.0"), "2x8"),
    ("L05", "S02", "Valve Line 2", "VALVES", Decimal("10.0"), "2x8"),
    ("L06", "S02", "Actuator Cell", "VALVES", Decimal("8.0"), "1x10"),
    ("L07", "S03", "Conveyor Frame Line", "CONVEYORS", Decimal("2.0"), "2x8"),
    ("L08", "S03", "Belt and Roller Line", "SPARE_PARTS", Decimal("30.0"), "2x8"),
    ("L09", "S03", "Conveyor Assembly Line", "CONVEYORS", Decimal("1.5"), "1x10"),
    ("L10", "S04", "Fabrication Bay 1", "FABRICATION", Decimal("1.0"), "1x10"),
    ("L11", "S04", "Fabrication Bay 2", "FABRICATION", Decimal("1.0"), "1x10"),
    ("L12", "S04", "Welding Cell", "FABRICATION", Decimal("2.0"), "2x8"),
    ("L13", "S05", "US Pump Line 1", "PUMPS", Decimal("6.0"), "2x8"),
    ("L14", "S05", "US Pump Line 2", "PUMPS", Decimal("5.0"), "2x8"),
    ("L15", "S05", "US Parts Cell", "SPARE_PARTS", Decimal("18.0"), "1x10"),
)
# Valve Line 2 has a worn press: more breakdowns, scrap and failed inspections.
# The Welding Cell has more weld defects.
PROBLEM_LINE = "L05"
WELDING_LINE = "L12"
# (sku, name, family, standard cost AUD, list price AUD, weight kg)
PRODUCTS = (
    ("FP-CEN-050", "Centrifugal Pump 50 mm", "PUMPS", 1850, 3200, 48),
    ("FP-CEN-100", "Centrifugal Pump 100 mm", "PUMPS", 3400, 5900, 95),
    ("FP-SLR-150", "Slurry Pump 150 mm", "PUMPS", 9800, 16500, 420),
    ("FP-SUB-075", "Submersible Pump 75 mm", "PUMPS", 2600, 4500, 60),
    ("FP-DOS-010", "Dosing Pump 10 L/h", "PUMPS", 780, 1450, 9),
    ("FP-FIR-080", "Fire Pump Set 80 mm", "PUMPS", 7400, 12800, 310),
    ("FV-BAL-050", "Ball Valve 50 mm", "VALVES", 180, 340, 6),
    ("FV-BUT-150", "Butterfly Valve 150 mm", "VALVES", 420, 790, 18),
    ("FV-GAT-100", "Gate Valve 100 mm", "VALVES", 610, 1150, 35),
    ("FV-CHK-080", "Check Valve 80 mm", "VALVES", 260, 495, 14),
    ("FV-ACT-ELE", "Electric Valve Actuator", "VALVES", 950, 1790, 12),
    ("FV-ACT-PNE", "Pneumatic Valve Actuator", "VALVES", 640, 1200, 8),
    ("FC-BLT-10M", "Belt Conveyor 10 m", "CONVEYORS", 14500, 24800, 1600),
    ("FC-BLT-25M", "Belt Conveyor 25 m", "CONVEYORS", 29800, 49500, 3800),
    ("FC-RLR-06M", "Roller Conveyor 6 m", "CONVEYORS", 6200, 10900, 700),
    ("FC-STK-30M", "Radial Stacker 30 m", "CONVEYORS", 68000, 112000, 9500),
    ("FF-TNK-020", "Stainless Tank 20 kL", "FABRICATION", 18500, 31000, 2400),
    ("FF-HOP-005", "Feed Hopper 5 m3", "FABRICATION", 7800, 13500, 1200),
    ("FF-SKD-PMP", "Pump Skid Frame", "FABRICATION", 3900, 6900, 450),
    ("FF-CHU-TRN", "Transfer Chute", "FABRICATION", 5200, 9100, 800),
    ("FS-IMP-100", "Impeller 100 mm", "SPARE_PARTS", 240, 520, 7),
    ("FS-SEL-KIT", "Mechanical Seal Kit", "SPARE_PARTS", 95, 240, 1),
    ("FS-BRG-SET", "Bearing Set", "SPARE_PARTS", 130, 290, 3),
    ("FS-IDL-ROL", "Idler Roller", "SPARE_PARTS", 45, 110, 6),
    ("FS-BLT-SPL", "Belt Splice Kit", "SPARE_PARTS", 160, 380, 4),
    ("FS-VLV-SEA", "Valve Seat Kit", "SPARE_PARTS", 38, 95, 1),
)
PRODUCT = {p[0]: p for p in PRODUCTS}
# How source systems spell each country; silver cleans these up.
RAW_COUNTRY = {"AU": ("AU", "AU", "Australia", "AUS"), "NZ": ("NZ", "New Zealand"), "SG": ("SG", "Singapore"),
               "GB": ("GB", "UK", "United Kingdom"), "US": ("US", "USA", "United States")}


def scripts() -> list[Script]:
    from . import production, quality, supply_chain

    operational = Script(
        path=f"{COMPANY.folder}/snowflake/{COMPANY.folder}.sql",
        title=COMPANY.name,
        description=(
            "Production, supply chain and quality data for Forgeline Industries, a manufacturer of "
            "industrial pumps, valves, conveyors and custom fabrication headquartered in Adelaide, "
            "with plants in New Zealand and the US. One schema per business, each with bronze, "
            "silver and gold tables."
        ),
        platform="snowflake",
        container=COMPANY.key,
        schemas=[production.schema(), supply_chain.schema(), quality.schema()],
    )
    return [operational, hr.script(COMPANY), marketing.script(COMPANY)]
