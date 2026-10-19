"""Quality: inspections of work orders, defects, non-conformance reports,
customer complaints and warranty claims from the quality management
system."""

from __future__ import annotations

from decimal import Decimal

from ... import fake, hr
from ...common import aud_sql, meta_columns
from ...model import At, Col, DaysAgo, Derived, Schema, Sql, Table
from . import COMPANY, PRODUCT, PROBLEM_LINE, WELDING_LINE, production, supply_chain

DEFECT_TYPES = {
    "PUMPS": ("POROSITY", "LEAK_TEST_FAIL", "DIMENSIONAL", "MISSING_COMPONENT", "PAINT_FINISH"),
    "VALVES": ("SEAT_LEAK", "DIMENSIONAL", "POROSITY", "THREAD_DAMAGE"),
    "CONVEYORS": ("WELD_CRACK", "ALIGNMENT", "PAINT_FINISH"),
    "FABRICATION": ("WELD_CRACK", "WELD_POROSITY", "DIMENSIONAL"),
    "SPARE_PARTS": ("DIMENSIONAL", "SURFACE_FINISH", "MATERIAL_HARDNESS"),
}
DISPOSITIONS = {"MINOR": ("USE_AS_IS", "REWORK"), "MAJOR": ("REWORK", "SCRAP"), "CRITICAL": ("SCRAP",)}
ROOT_CAUSES = ("MATERIAL", "METHOD", "MACHINE", "PEOPLE", "MEASUREMENT")
CORRECTIVE_ACTIONS = {
    "MATERIAL": "Supplier asked for an 8D report. Incoming inspection increased to 100% for the next five lots.",
    "METHOD": "Work instruction updated and operators retrained.",
    "MACHINE": "Press tooling replaced. Maintenance to check wear every 500 cycles.",
    "PEOPLE": "Operator coached; second person check added for this step.",
    "MEASUREMENT": "Gauge recalibrated; measurement system analysis scheduled.",
}
COMPLAINTS = {
    "PRODUCT_DEFECT": ("{product} on order {order} is leaking after {weeks} weeks. Our planner {contact} ({phone}) needs a replacement before the shutdown.",
                       "{product} arrived with a cracked housing. Photos sent by {contact}. Please collect from {address}."),
    "DELIVERY": ("Order {order} arrived {days} days late and held up commissioning. Please call {contact} on {phone}.",
                 "Only part of order {order} was delivered. {contact} has been chasing for a week ({email})."),
    "SAFETY": ("Seal failed on the {product} and sprayed hot water; our operator {injured} was treated for burns at {hospital}. We need an incident report urgently. Contact {contact}, {phone}.",),
    "SERVICE": ("{product} keeps tripping. Your technician has been out twice. Contact {email} to arrange a third visit.",),
    "BILLING": ("Invoice for order {order} does not match the quoted discount. Accounts payable contact {contact}, {email}.",),
}
COMPLAINT_WEIGHTS = {"PRODUCT_DEFECT": 45, "DELIVERY": 25, "SAFETY": 5, "SERVICE": 15, "BILLING": 10}
HOSPITALS = ("Royal Adelaide Hospital", "Gold Coast University Hospital", "Fiona Stanley Hospital", "Middlemore Hospital",
             "St Thomas' Hospital", "Baylor Scott & White", "Changi General Hospital")
FAILURE_MODES = {
    "PUMPS": ("SEAL_FAILURE", "BEARING_FAILURE", "IMPELLER_WEAR", "MOTOR_FAILURE"),
    "VALVES": ("SEAT_LEAK", "ACTUATOR_FAULT", "STEM_LEAK"),
    "CONVEYORS": ("BELT_DAMAGE", "IDLER_FAILURE", "GEARBOX_FAILURE"),
    "FABRICATION": ("WELD_FAILURE", "CORROSION"),
    "SPARE_PARTS": ("PREMATURE_WEAR",),
}
META = ("QMS", "qms-0412")


def bronze() -> list[Table]:
    m = meta_columns()
    staff = hr.staff_in(COMPANY, "QUALITY")
    inspectors = [s for s in staff if s["title"] in ("Quality Inspector", "Head of Quality")]
    engineers = [s for s in staff if s["title"] in ("Quality Engineer", "Head of Quality")]

    r = fake.rng("forgeline", "quality", "inspections")
    inspections, defect_rows = [], []
    for w in production.work_orders():
        if w["status"] != "COMPLETED" or not fake.chance(r, 0.85):
            continue
        family = PRODUCT[w["sku"]][2]
        fail_chance = 0.25 if w["line"] == PROBLEM_LINE else 0.18 if w["line"] == WELDING_LINE else 0.05
        kinds = ["FINAL"] + (["FIRST_ARTICLE"] if fake.chance(r, 0.08) else [])
        for kind in kinds:
            sample = w["produced"] if family in ("CONVEYORS", "FABRICATION") else min(w["produced"], r.randint(3, 20 if family == "PUMPS" else 50))
            if fake.chance(r, fail_chance):
                defects = r.randint(1, max(1, sample // 4))
                result = "CONDITIONAL" if fake.chance(r, 0.3) else "FAIL"
            else:
                defects = 1 if fake.chance(r, 0.08) else 0
                result = "PASS"
            inspection = {"id": f"INS{len(inspections) + 1:06d}", "work_order": w, "kind": kind, "sample": sample,
                          "defects": defects, "result": result, "inspector": r.choice(inspectors),
                          "days_ago": w["days_ago"], "minute": w["start"] + w["run_minutes"] + r.randint(10, 120)}
            inspections.append(inspection)
            remaining = defects
            while remaining:
                quantity = r.randint(1, remaining)
                remaining -= quantity
                defect_type = "SEAT_LEAK" if w["line"] == PROBLEM_LINE and fake.chance(r, 0.7) else r.choice(DEFECT_TYPES[family])
                severity = "MINOR" if result == "PASS" else fake.weighted(r, {"MINOR": 45, "MAJOR": 42, "CRITICAL": 13})
                inspector = inspection["inspector"]
                note = f"{inspector['first_name']} {inspector['last_name']}: {defect_type.lower().replace('_', ' ')} on {quantity} of {sample} units."
                if w["line"] == PROBLEM_LINE:
                    note += " Press 2 tooling looks worn again."
                defect_rows.append((f"DEF{len(defect_rows) + 1:06d}", inspection["id"], defect_type, severity, quantity,
                                    r.choice(DISPOSITIONS[severity]), note, *META))
    inspection_rows = [
        (i["id"], i["work_order"]["id"], i["work_order"]["sku"], At(i["days_ago"], i["minute"]), i["kind"], i["sample"], i["defects"],
         r.choice((i["result"], i["result"].title(), i["result"].lower())), i["inspector"]["employee_id"], *META)
        for i in inspections
    ]

    r = fake.rng("forgeline", "quality", "complaints")
    delivered = [o for o in supply_chain.sales_orders() if o["delivered"] is not None]
    complaints = []
    for i in range(110):
        # Valves from the Geelong plant draw more complaints.
        order = r.choice([o for o in delivered if o["site"] == "S02"] if fake.chance(r, 0.35) else delivered)
        customer = order["customer"]
        category = fake.weighted(r, COMPLAINT_WEIGHTS)
        received = max(order["delivered"] - r.randint(1, 60), 0)
        if received > 30:
            status = fake.weighted(r, {"CLOSED": 80, "RESOLVED": 12, "IN_PROGRESS": 8})
        else:
            status = fake.weighted(r, {"OPEN": 40, "IN_PROGRESS": 40, "RESOLVED": 20})
        closed = max(received - r.randint(1, 30), 0) if status in ("RESOLVED", "CLOSED") else None
        contact = f"{customer['contact_first']} {customer['contact_last']}"
        a = customer["address"]
        text = r.choice(COMPLAINTS[category]).format(
            product=PRODUCT[order["sku"]][1], order=order["id"], weeks=r.randint(1, 12), contact=contact, phone=customer["phone"],
            address=f"{a['address_line']}, {a['suburb']} {a['state']} {a['postcode']}", days=r.randint(3, 20),
            email=customer["email"], injured=" ".join(fake.name(r)), hospital=r.choice(HOSPITALS),
        )
        severity = "CRITICAL" if category == "SAFETY" else fake.weighted(r, {"LOW": 30, "MEDIUM": 45, "HIGH": 25})
        complaints.append({"id": f"CMP{i + 1:05d}", "order": order, "category": category, "received": received, "status": status,
                           "closed": closed, "severity": severity, "contact": contact, "text": text})
    complaint_rows = [
        (c["id"], c["order"]["customer"]["id"], c["order"]["id"], c["order"]["sku"], At(c["received"], fake.minute_of_day(r, 7, 18)),
         fake.weighted(r, {"EMAIL": 45, "PHONE": 30, "PORTAL": 15, "ACCOUNT_MANAGER": 10}), c["category"], c["severity"], c["contact"],
         c["order"]["customer"]["email"], c["order"]["customer"]["phone"], c["text"], c["status"],
         DaysAgo(c["closed"]) if c["closed"] is not None else None, r.choice(engineers)["employee_id"], *META)
        for c in complaints
    ]

    r = fake.rng("forgeline", "quality", "ncrs")
    failed = [i for i in inspections if i["result"] != "PASS"]
    ncr_rows = []
    for n in range(100):
        source = "INTERNAL" if n < 55 else "SUPPLIER" if n < 85 else "CUSTOMER"
        supplier_id = complaint_id = work_order_id = None
        if source == "INTERNAL":
            inspection = r.choice(failed)
            w = inspection["work_order"]
            raised, sku, site, work_order_id = w["days_ago"], w["sku"], w["site"], w["id"]
            cause = "MACHINE" if w["line"] == PROBLEM_LINE else r.choice(ROOT_CAUSES)
            description = f"Inspection {inspection['id']} {inspection['result'].lower()}: {inspection['defects']} defects on work order {w['id']}."
        elif source == "SUPPLIER":
            supplier = r.choice([s for s in supply_chain.suppliers() if s["category"] in ("CASTINGS", "STEEL", "SEALS", "BEARINGS")])
            supplier_id, raised, cause = supplier["id"], r.randint(0, 240), "MATERIAL"
            w = r.choice(production.work_orders())
            sku, site = w["sku"], w["site"]
            description = f"Incoming {supplier['category'].lower()} from {supplier['name']} out of tolerance. Lot quarantined."
        else:
            complaint = r.choice([c for c in complaints if c["category"] in ("PRODUCT_DEFECT", "SAFETY")])
            complaint_id, raised, sku, site = complaint["id"], complaint["received"], complaint["order"]["sku"], complaint["order"]["site"]
            cause = r.choice(ROOT_CAUSES)
            description = f"Raised from customer complaint {complaint['id']} about {PRODUCT[sku][1]}."
        status = fake.weighted(r, {"CLOSED": 85, "INVESTIGATING": 15}) if raised > 60 else fake.weighted(r, {"OPEN": 40, "INVESTIGATING": 45, "CLOSED": 15})
        closed = max(raised - r.randint(5, 60), 0) if status == "CLOSED" else None
        ncr_rows.append((
            f"NCR{n + 1:05d}", DaysAgo(raised), source, site, sku, work_order_id, supplier_id, complaint_id, description, cause,
            status, DaysAgo(closed) if closed is not None else None, fake.money(r, 200, 25000 if source == "CUSTOMER" else 8000),
            CORRECTIVE_ACTIONS[cause] if status == "CLOSED" else None, r.choice(engineers)["employee_id"], *META,
        ))

    r = fake.rng("forgeline", "quality", "warranty")
    claimable = [o for o in delivered if o["family"] != "SPARE_PARTS"]
    warranty_rows = []
    for n in range(130):
        order = r.choice(claimable)
        claim_days = max(order["delivered"] - r.randint(14, 180), 0)
        status = "PENDING" if claim_days < 14 and fake.chance(r, 0.7) else fake.weighted(r, {"APPROVED": 80, "REJECTED": 20})
        claimed = (order["unit_price"] * fake.rate(r, 0.1, 0.6)).quantize(Decimal("0.01"))
        approved = None if status == "PENDING" else Decimal("0.00") if status == "REJECTED" else (claimed * fake.rate(r, 0.7, 1.0)).quantize(Decimal("0.01"))
        mode = r.choice(FAILURE_MODES[order["family"]])
        warranty_rows.append((
            f"WAR{n + 1:05d}", order["customer"]["id"], order["id"], order["sku"], f"{order['sku']}-{fake.digits(r, 6)}", DaysAgo(claim_days),
            mode, f"{mode.replace('_', ' ').capitalize()} reported by {order['customer']['contact_first']} at the customer's site.",
            claimed, approved, order["currency"], status, *META,
        ))

    return [
        Table("bronze_inspections", "Final and first article inspections of completed work orders. result is entered by hand: PASS, Pass, pass...", [
            Col("inspection_id", "string"), Col("work_order_id", "string"), Col("sku", "string"), Col("inspected_at", "timestamp"),
            Col("inspection_type", "string"), Col("sample_size", "int"), Col("defects_found", "int"), Col("result", "string"),
            Col("inspector_employee_id", "string", "Matches employee_id in the HR data"), *m], inspection_rows),
        Table("bronze_defects", "Defects found at inspection, with severity and what was done with the units.", [
            Col("defect_id", "string"), Col("inspection_id", "string"), Col("defect_type", "string"), Col("severity", "string"),
            Col("quantity", "int"), Col("disposition", "string", "USE_AS_IS, REWORK or SCRAP"),
            Col("notes", "text", "Free text: inspector names"), *m], defect_rows),
        Table("bronze_non_conformances", "Non-conformance reports raised from inspections, supplier deliveries and customer complaints.", [
            Col("ncr_id", "string"), Col("raised_date", "date"), Col("ncr_source", "string", "INTERNAL, SUPPLIER or CUSTOMER"),
            Col("site_id", "string"), Col("sku", "string"), Col("work_order_id", "string"), Col("supplier_id", "string"),
            Col("complaint_id", "string"), Col("description", "text"), Col("root_cause_category", "string"), Col("ncr_status", "string"),
            Col("closed_date", "date"), Col("cost_of_quality_aud", "decimal(12,2)", "Rework, scrap and containment cost"),
            Col("corrective_action", "text"), Col("owner_employee_id", "string", "Matches employee_id in the HR data"), *m], ncr_rows),
        Table("bronze_customer_complaints", "Customer complaints about products, deliveries, safety, service and billing.", [
            Col("complaint_id", "string"), Col("customer_id", "string"), Col("order_id", "string"), Col("sku", "string"),
            Col("received_at", "timestamp"), Col("channel", "string"), Col("category", "string"), Col("severity", "string"),
            Col("contact_name", "string", "Person name"), Col("contact_email", "string", "PII: email"),
            Col("contact_phone", "string", "PII: phone number"),
            Col("complaint_text", "text", "Free text: names, phone numbers, emails, addresses and injuries to customer staff"),
            Col("complaint_status", "string"), Col("closed_date", "date"),
            Col("assigned_employee_id", "string", "Matches employee_id in the HR data"), *m], complaint_rows),
        Table("bronze_warranty_claims", "Warranty claims on delivered products. approved_amount is empty while a claim is pending.", [
            Col("claim_id", "string"), Col("customer_id", "string"), Col("order_id", "string"), Col("sku", "string"),
            Col("serial_number", "string"), Col("claim_date", "date"), Col("failure_mode", "string"), Col("failure_description", "text"),
            Col("claimed_amount", "decimal(12,2)"), Col("approved_amount", "decimal(12,2)"), Col("currency", "string"),
            Col("claim_status", "string"), *m], warranty_rows),
    ]


def silver() -> list[Derived]:
    def inspections_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH base AS (
  SELECT i.*, UPPER(TRIM(i.result)) AS clean_result
  FROM {s.ref('bronze_inspections')} i
)
SELECT
  i.inspection_id,
  i.work_order_id,
  i.sku,
  w.product_name,
  w.product_family,
  i.inspected_at,
  CAST(i.inspected_at AS DATE) AS inspection_date,
  {d.month_start('CAST(i.inspected_at AS DATE)')} AS inspection_month,
  i.inspection_type,
  i.sample_size,
  i.defects_found,
  {d.pct('i.defects_found', 'i.sample_size')} AS defect_rate_pct,
  i.clean_result AS result,
  CASE WHEN i.clean_result = 'PASS' THEN TRUE ELSE FALSE END AS is_pass,
  i.inspector_employee_id,
  w.line_id,
  w.line_name,
  w.site_id,
  w.site_name,
  w.country,
  w.region
FROM base i
JOIN {s.ref('production.silver_work_orders')} w ON w.work_order_id = i.work_order_id"""

    def defects_sql(s: Sql) -> str:
        return f"""
SELECT df.defect_id, df.inspection_id, i.work_order_id, i.sku, i.product_family, i.inspection_date, df.defect_type, df.severity,
       df.quantity, df.disposition, df.notes, i.line_id, i.site_id, i.country, i.region
FROM {s.ref('bronze_defects')} df
JOIN {s.ref('silver_inspections')} i ON i.inspection_id = df.inspection_id"""

    def ncrs_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  ncr.ncr_id,
  ncr.raised_date,
  {d.month_start('ncr.raised_date')} AS raised_month,
  ncr.ncr_source,
  ncr.site_id,
  si.site_name,
  ncr.sku,
  pr.product_name,
  pr.product_family,
  ncr.work_order_id,
  ncr.supplier_id,
  ncr.complaint_id,
  ncr.description,
  ncr.root_cause_category,
  ncr.ncr_status,
  CASE WHEN ncr.ncr_status = 'CLOSED' THEN FALSE ELSE TRUE END AS is_open,
  ncr.closed_date,
  {d.days_between('ncr.raised_date', f'COALESCE(ncr.closed_date, {d.today})')} AS days_open,
  ncr.cost_of_quality_aud,
  ncr.corrective_action,
  ncr.owner_employee_id,
  si.country,
  si.region
FROM {s.ref('bronze_non_conformances')} ncr
JOIN {s.ref('production.silver_sites')} si ON si.site_id = ncr.site_id
JOIN {s.ref('production.silver_products')} pr ON pr.sku = ncr.sku"""

    def complaints_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  cc.complaint_id,
  cc.customer_id,
  c.customer_name,
  c.industry,
  cc.order_id,
  cc.sku,
  pr.product_name,
  pr.product_family,
  cc.received_at,
  CAST(cc.received_at AS DATE) AS received_date,
  cc.channel,
  cc.category,
  cc.severity,
  cc.contact_name,
  LOWER(TRIM(cc.contact_email)) AS contact_email,
  cc.contact_phone,
  cc.complaint_text,
  cc.complaint_status,
  CASE WHEN cc.complaint_status IN ('OPEN', 'IN_PROGRESS') THEN TRUE ELSE FALSE END AS is_open,
  cc.closed_date,
  {d.days_between('cc.received_at', f'COALESCE(cc.closed_date, {d.today})')} AS days_open,
  cc.assigned_employee_id,
  c.country,
  c.region
FROM {s.ref('bronze_customer_complaints')} cc
JOIN {s.ref('supply_chain.silver_customers')} c ON c.customer_id = cc.customer_id
JOIN {s.ref('production.silver_products')} pr ON pr.sku = cc.sku"""

    def warranty_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  wc.claim_id,
  wc.customer_id,
  so.customer_name,
  wc.order_id,
  wc.sku,
  so.product_name,
  so.product_family,
  wc.serial_number,
  wc.claim_date,
  {d.month_start('wc.claim_date')} AS claim_month,
  {d.days_between('so.delivered_date', 'wc.claim_date')} AS days_after_delivery,
  wc.failure_mode,
  wc.failure_description,
  wc.claimed_amount,
  wc.approved_amount,
  wc.currency,
  {aud_sql('wc.claimed_amount', 'wc.currency', d.money)} AS claimed_amount_aud,
  {aud_sql('wc.approved_amount', 'wc.currency', d.money)} AS approved_amount_aud,
  wc.claim_status,
  so.ship_from_site_id,
  so.country,
  so.region
FROM {s.ref('bronze_warranty_claims')} wc
JOIN {s.ref('supply_chain.silver_sales_orders')} so ON so.order_id = wc.order_id"""

    return [
        Derived("silver_inspections", "Inspections with clean result, pass flag, defect rate, product, line and the site's region.", inspections_sql),
        Derived("silver_defects", "Defects with the inspection's product, line, site and region.", defects_sql),
        Derived("silver_non_conformances", "Non-conformance reports with product, open flag, days open and the site's region.", ncrs_sql),
        Derived("silver_customer_complaints", "Complaints with customer, product, open flag, days open and the customer's region.", complaints_sql),
        Derived("silver_warranty_claims", "Warranty claims with customer, product, days after delivery, AUD amounts and the customer's region.", warranty_sql),
    ]


def gold() -> list[Derived]:
    def first_pass_yield_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  inspection_month,
  site_id,
  site_name,
  line_id,
  line_name,
  product_family,
  region,
  COUNT(*) AS inspections,
  SUM(CASE WHEN is_pass THEN 1 ELSE 0 END) AS passed,
  {d.pct('SUM(CASE WHEN is_pass THEN 1 ELSE 0 END)', 'COUNT(*)')} AS first_pass_yield_pct,
  SUM(sample_size) AS units_inspected,
  SUM(defects_found) AS defects_found,
  {d.pct('SUM(defects_found)', 'SUM(sample_size)')} AS defects_per_100_units
FROM {s.ref('silver_inspections')}
GROUP BY 1, 2, 3, 4, 5, 6, 7"""

    def complaint_overview_sql(s: Sql) -> str:
        return f"""
WITH warranty AS (
  SELECT order_id, COUNT(*) AS warranty_claims, SUM(approved_amount_aud) AS warranty_approved_aud
  FROM {s.ref('silver_warranty_claims')}
  GROUP BY order_id
),
ncrs AS (
  SELECT complaint_id, MIN(ncr_id) AS ncr_id FROM {s.ref('silver_non_conformances')} WHERE complaint_id IS NOT NULL GROUP BY complaint_id
)
SELECT
  cc.complaint_id,
  cc.received_date,
  cc.customer_id,
  cc.customer_name,
  cc.industry,
  cc.contact_name,
  cc.contact_email,
  cc.contact_phone,
  cc.order_id,
  cc.sku,
  cc.product_name,
  cc.product_family,
  cc.category,
  cc.severity,
  cc.complaint_status,
  cc.is_open,
  cc.days_open,
  COALESCE(wa.warranty_claims, 0) AS warranty_claims_on_order,
  COALESCE(wa.warranty_approved_aud, 0) AS warranty_approved_aud,
  n.ncr_id,
  cc.complaint_text,
  cc.assigned_employee_id,
  cc.country,
  cc.region
FROM {s.ref('silver_customer_complaints')} cc
LEFT JOIN warranty wa ON wa.order_id = cc.order_id
LEFT JOIN ncrs n ON n.complaint_id = cc.complaint_id"""

    def cost_of_quality_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH costs AS (
  SELECT {d.month_start('scheduled_date')} AS cost_month, site_id, scrap_cost_aud, 0 AS ncr_cost_aud, 0 AS warranty_cost_aud
  FROM {s.ref('production.silver_work_orders')}
  WHERE work_order_status IN ('COMPLETED', 'IN_PROGRESS')
  UNION ALL
  SELECT raised_month, site_id, 0, cost_of_quality_aud, 0
  FROM {s.ref('silver_non_conformances')}
  UNION ALL
  SELECT claim_month, ship_from_site_id, 0, 0, COALESCE(approved_amount_aud, 0)
  FROM {s.ref('silver_warranty_claims')}
)
SELECT
  c.cost_month,
  c.site_id,
  si.site_name,
  si.region,
  SUM(c.scrap_cost_aud) AS scrap_cost_aud,
  SUM(c.ncr_cost_aud) AS ncr_cost_aud,
  SUM(c.warranty_cost_aud) AS warranty_cost_aud,
  SUM(c.scrap_cost_aud + c.ncr_cost_aud + c.warranty_cost_aud) AS total_cost_of_quality_aud
FROM costs c
JOIN {s.ref('production.silver_sites')} si ON si.site_id = c.site_id
GROUP BY 1, 2, 3, 4"""

    return [
        Derived("gold_first_pass_yield", "Inspections by month, site, line and product family: first pass yield and defects per 100 units inspected.", first_pass_yield_sql),
        Derived("gold_complaint_overview", "One row per complaint: customer and contact, product, severity, status, days open, related warranty claims and NCR, and the complaint text.", complaint_overview_sql),
        Derived("gold_cost_of_quality", "Cost of quality by month and site in AUD: scrap from production, non-conformances and approved warranty claims.", cost_of_quality_sql),
    ]


def schema() -> Schema:
    return Schema(
        "quality",
        "Forgeline Quality",
        "Quality: inspections, defects, non-conformance reports, customer complaints and warranty claims. "
        "Source: the quality management system (QMS).",
        bronze(), silver(), gold(),
    )
