"""Production: sites, production lines, the product master, work orders,
downtime and safety incidents from the manufacturing execution system."""

from __future__ import annotations

from decimal import Decimal

from ... import fake, hr
from ...common import meta_columns, region_sql
from ...model import At, Col, DaysAgo, Derived, Schema, Sql, Table
from . import COMPANY, LINES, PRODUCTS, PROBLEM_LINE, SITES

SHIFTS = {"3x8": (("DAY", 360), ("AFTERNOON", 840), ("NIGHT", 1320)), "2x8": (("DAY", 360), ("AFTERNOON", 840)),
          "1x10": (("DAY", 420),)}
# Minutes the line is scheduled to run each day, by shift pattern.
SCHEDULED_MINUTES = {"3x8": 1440, "2x8": 960, "1x10": 600}
# (minutes range, weight on a normal line, weight on the problem line)
DOWNTIME = {
    "MECHANICAL": ((20, 240), 20, 55), "ELECTRICAL": ((15, 180), 12, 10), "CHANGEOVER": ((20, 90), 25, 12),
    "MATERIAL_SHORTAGE": ((30, 300), 14, 8), "QUALITY_HOLD": ((30, 240), 8, 10), "PLANNED_MAINTENANCE": ((60, 480), 13, 3),
    "OPERATOR_UNAVAILABLE": ((15, 120), 8, 2),
}
COMMENTS = {
    "MECHANICAL": ("Hydraulic press on {line} lost pressure again. Called {tech} from maintenance on {phone}. Seal replaced.",
                   "Bearing noise on the spindle. {tech} says the replacement part is on back order.",
                   "Conveyor jammed at the infeed. {tech} cleared it and adjusted the guides."),
    "ELECTRICAL": ("Drive tripped on overcurrent. Electrician {tech} reset it and checked the motor.",
                   "PLC fault after the power dip. {tech} reloaded the program."),
    "CHANGEOVER": ("Changeover to {sku}. Took longer than planned because tooling was missing.", "Changeover to {sku}."),
    "MATERIAL_SHORTAGE": ("Waiting on castings from the foundry. Buyer chasing, ETA tomorrow.",
                          "Ran out of seal kits for {sku}. Stores recount requested."),
    "QUALITY_HOLD": ("Line held after leak test failures on {sku}. Quality reviewing the batch; {tech} checking the leak tester.",),
    "PLANNED_MAINTENANCE": ("Scheduled preventive maintenance.", "Annual pressure vessel inspection."),
    "OPERATOR_UNAVAILABLE": ("Operator {operator} called in sick with {illness}. No cover until 10am.",
                             "Operator {operator} left early for a medical appointment ({illness})."),
}
ILLNESSES = ("gastro", "a migraine", "a back injury", "COVID-19", "the flu", "a sprained wrist")
INCIDENT_TYPES = {"INJURY": 40, "NEAR_MISS": 35, "PROPERTY_DAMAGE": 18, "ENVIRONMENTAL": 7}
INJURIES = (("Laceration", "hand", "cut {pronoun} hand on a sharp casting edge"),
            ("Burn", "forearm", "burned {pronoun} forearm on a hot weld"),
            ("Strain", "lower back", "strained {pronoun} lower back lifting a pump housing"),
            ("Crush", "finger", "crushed {pronoun} finger in a press guard"),
            ("Foreign body", "eye", "got a metal fragment in {pronoun} eye while grinding"),
            ("Hearing", "ears", "reported ringing in {pronoun} ears after the compressor alarm"))
NEAR_MISSES = ("Forklift reversed past a pedestrian in the {area} without a spotter.",
               "Load slipped from an overhead crane sling in the {area}. Nobody was underneath.",
               "Guard found bypassed on a press in the {area}.")
OTHER_INCIDENTS = {"PROPERTY_DAMAGE": "Forklift hit a racking upright in the {area}. Racking unloaded and tagged out.",
                   "ENVIRONMENTAL": "Hydraulic oil leak of about 20 litres in the {area}. Spill kit used and the drain covered."}
AREAS = ("machine shop", "assembly area", "paint booth", "loading dock", "warehouse", "test bay")
META = ("MES", "mes-0412")

_work_orders: list[dict] | None = None


def work_orders() -> list[dict]:
    """Work orders for the last four months and the next ten days. Quality
    inspects completed ones."""
    global _work_orders
    if _work_orders is not None:
        return _work_orders
    r = fake.rng("forgeline", "production", "work_orders")
    supervisors = [s for s in hr.staff_in(COMPANY, "PRODUCTION") if s["title"] in ("Production Supervisor", "General Manager Operations")]
    result = []
    for line_id, site_id, _, family, rated, pattern in LINES:
        skus = [p for p in PRODUCTS if p[2] == family]
        for days_ago in range(-10, 121):
            if not fake.chance(r, 0.42):
                continue
            sku = r.choice(skus)
            shift, start = r.choice(SHIFTS[pattern])
            planned = max(1, int(rated * Decimal(r.randint(5, 14))))
            if days_ago < 0:
                status, produced, scrap = "RELEASED", None, None
            elif days_ago == 0:
                status = "IN_PROGRESS"
                produced = int(planned * fake.rate(r, 0.2, 0.7))
                scrap = int(produced * fake.rate(r, 0.0, 0.03))
            else:
                status = fake.weighted(r, {"COMPLETED": 95, "CANCELLED": 5})
                if status == "CANCELLED":
                    produced, scrap = 0, 0
                else:
                    problem = line_id == PROBLEM_LINE
                    produced = max(1, round(planned * fake.rate(r, *((0.7, 0.95) if problem else (0.88, 1.05)))))
                    scrap = round(produced * fake.rate(r, *((0.04, 0.10) if problem else (0.0, 0.03))))
            result.append({
                "id": f"WO{4000001 + len(result)}", "line": line_id, "site": site_id, "sku": sku[0], "days_ago": days_ago,
                "shift": shift, "start": start + r.randint(0, 30), "run_minutes": r.randint(300, 470), "planned": planned,
                "produced": produced, "scrap": scrap, "status": status, "supervisor": r.choice(supervisors)["employee_id"],
            })
    _work_orders = result
    return result


def bronze() -> list[Table]:
    m = meta_columns()
    orders = work_orders()

    site_rows = [(*s, *("ERP", "erp-0412")) for s in SITES]
    r = fake.rng("forgeline", "production", "lines")
    line_rows = [(l[0], l[1], l[2], l[3], l[4], l[5], DaysAgo(r.randint(365 * 2, 365 * 25)), *META) for l in LINES]
    product_rows = [(p[0], p[1], p[2], "EACH", Decimal(p[3]), Decimal(p[4]), "AUD", Decimal(p[5]), True, "ERP", "erp-0412")
                    for p in PRODUCTS]

    r = fake.rng("forgeline", "production", "work_order_rows")
    work_order_rows = []
    for w in orders:
        started = w["status"] in ("COMPLETED", "IN_PROGRESS")
        work_order_rows.append((
            w["id"], w["line"], w["sku"], DaysAgo(w["days_ago"]), w["shift"],
            At(w["days_ago"], w["start"]) if started else None,
            At(w["days_ago"], w["start"] + w["run_minutes"]) if w["status"] == "COMPLETED" else None,
            w["planned"], w["produced"], w["scrap"], r.choice((w["status"], w["status"].lower())), w["supervisor"], *META,
        ))

    r = fake.rng("forgeline", "production", "downtime")
    staff = hr.staff_in(COMPANY, "PRODUCTION")
    techs = [s for s in staff if s["department"]["department_name"] == "Maintenance"]
    operators = [s for s in staff if s["title"] in ("Machine Operator", "Fitter and Turner", "Welder")]
    line_names = {l[0]: l[2] for l in LINES}
    events = []
    for w in orders:
        if w["status"] not in ("COMPLETED", "IN_PROGRESS"):
            continue
        problem = w["line"] == PROBLEM_LINE
        for _ in range(r.randint(1, 2) if problem else 1 if fake.chance(r, 0.55) else 0):
            reason = fake.weighted(r, {k: v[2] if problem else v[1] for k, v in DOWNTIME.items()})
            tech, operator = r.choice(techs), r.choice(operators)
            comment = r.choice(COMMENTS[reason]).format(
                line=line_names[w["line"]], tech=f"{tech['first_name']} {tech['last_name']}", phone=fake.phone(r, "AU"),
                sku=w["sku"], operator=f"{operator['first_name']} {operator['last_name']}", illness=r.choice(ILLNESSES),
            )
            events.append([
                f"DT{len(events) + 1:06d}", w["line"], w["id"], At(w["days_ago"], w["start"] + r.randint(10, 280)),
                r.randint(*DOWNTIME[reason][0]), reason, comment, r.choice(operators)["employee_id"], *META,
            ])
    # The MES re-sends some events after a network drop; silver removes them.
    duplicates = [list(e) for e in r.sample(events, 10)]
    for e in duplicates:
        e[-1] = "mes-0413"
    downtime_rows = [tuple(e) for e in events + duplicates]

    r = fake.rng("forgeline", "production", "incidents")
    advisors = [s for s in staff if s["department"]["department_name"] == "Health and Safety"]
    plants = [s for s in SITES if s[2] == "PLANT"]
    incident_rows = []
    for i in range(90):
        site = r.choice(plants)
        incident_type = fake.weighted(r, INCIDENT_TYPES)
        area = r.choice(AREAS)
        days_ago = r.randint(0, 365)
        injured = injury = body_part = treatment = claim = None
        lost_days = 0
        if incident_type == "INJURY":
            person = r.choice(operators)
            injury, body_part, what = r.choice(INJURIES)
            pronoun = {"F": "her", "M": "his"}.get(person.get("gender", ""), "their")
            treatment = fake.weighted(r, {"FIRST_AID": 50, "GP": 30, "HOSPITAL": 20})
            lost_days = 0 if treatment == "FIRST_AID" else r.choice((0, 0, 1, 2, 3, 5, 10, 20))
            severity = "HIGH" if treatment == "HOSPITAL" else "MEDIUM" if lost_days else "LOW"
            injured = person["employee_id"]
            claim = f"WC{fake.digits(r, 8)}" if lost_days >= 5 else None
            description = (f"{person['first_name']} {person['last_name']} {what.format(pronoun=pronoun)} in the {area}. "
                           f"Treated: {treatment.lower().replace('_', ' ')}.")
            if treatment == "HOSPITAL":
                description += f" Taken to hospital; partner contacted on {fake.phone(r, site[7])}."
            if injury == "Strain" and fake.chance(r, 0.5):
                description += " Worker disclosed a previous back surgery."
        elif incident_type == "NEAR_MISS":
            severity = fake.weighted(r, {"LOW": 40, "MEDIUM": 45, "HIGH": 15})
            description = r.choice(NEAR_MISSES).format(area=area)
        else:
            severity = fake.weighted(r, {"LOW": 50, "MEDIUM": 40, "HIGH": 10})
            description = OTHER_INCIDENTS[incident_type].format(area=area)
        incident_rows.append((
            f"INC{i + 1:05d}", site[0], At(days_ago, fake.minute_of_day(r, 6, 23)), incident_type, severity, injured, injury,
            body_part, treatment, lost_days, claim, description, r.choice(advisors)["employee_id"], "SAFETYHUB", "sh-0412",
        ))

    return [
        Table("bronze_sites", "Forgeline plants, warehouses and service centres.", [
            Col("site_id", "string"), Col("site_name", "string"), Col("site_type", "string", "PLANT, WAREHOUSE or SERVICE_CENTRE"),
            Col("suburb", "string"), Col("city", "string"), Col("state", "string"), Col("postcode", "string"),
            Col("country", "string"), *m], site_rows),
        Table("bronze_production_lines", "Production lines in each plant, with the rated output and shift pattern.", [
            Col("line_id", "string"), Col("site_id", "string"), Col("line_name", "string"), Col("product_family", "string"),
            Col("rated_units_per_hour", "decimal(6,1)"), Col("shift_pattern", "string", "3x8, 2x8 or 1x10 hour shifts"),
            Col("commissioned_date", "date"), *m], line_rows),
        Table("bronze_products", "The product master: pumps, valves, conveyors, fabrication and spare parts, with standard cost and list price.", [
            Col("sku", "string"), Col("product_name", "string"), Col("product_family", "string"), Col("unit_of_measure", "string"),
            Col("standard_cost", "decimal(12,2)", "Commercially sensitive"), Col("list_price", "decimal(12,2)"),
            Col("currency", "string"), Col("weight_kg", "decimal(10,1)"), Col("is_active", "bool"), *m], product_rows),
        Table("bronze_work_orders", "Work orders for the last four months and the next ten days. Quantities are empty until a work order starts.", [
            Col("work_order_id", "string"), Col("line_id", "string"), Col("sku", "string"), Col("scheduled_date", "date"),
            Col("shift_name", "string"), Col("started_at", "timestamp"), Col("completed_at", "timestamp"),
            Col("planned_qty", "int"), Col("produced_qty", "int"), Col("scrap_qty", "int"), Col("work_order_status", "string"),
            Col("supervisor_employee_id", "string", "Matches employee_id in the HR data"), *m], work_order_rows),
        Table("bronze_downtime_events", "Line stoppages logged by operators. The MES re-sends some events.", [
            Col("event_id", "string"), Col("line_id", "string"), Col("work_order_id", "string"), Col("started_at", "timestamp"),
            Col("duration_minutes", "int"), Col("reason_code", "string"),
            Col("operator_comment", "text", "Free text: staff names, phone numbers and staff illnesses"),
            Col("reported_by_employee_id", "string", "Matches employee_id in the HR data"), *m], downtime_rows),
        Table("bronze_safety_incidents", "Workplace health and safety incidents for the last 12 months: injuries, near misses, damage and spills.", [
            Col("incident_id", "string"), Col("site_id", "string"), Col("occurred_at", "timestamp"), Col("incident_type", "string"),
            Col("severity", "string"), Col("injured_employee_id", "string", "Matches employee_id in the HR data"),
            Col("injury_type", "string", "Health information"), Col("body_part", "string", "Health information"),
            Col("treatment", "string", "Health information: FIRST_AID, GP or HOSPITAL"), Col("lost_time_days", "int"),
            Col("workers_comp_claim_number", "string", "Sensitive: workers compensation claim"),
            Col("description", "text", "Free text, health information: injured worker's name, injury, medical history and phone numbers"),
            Col("reported_by_employee_id", "string"), *m], incident_rows),
    ]


def silver() -> list[Derived]:
    def sites_sql(s: Sql) -> str:
        return f"""
SELECT site_id, site_name, site_type, suburb, city, state, postcode, country, {region_sql('country')} AS region
FROM {s.ref('bronze_sites')}"""

    def lines_sql(s: Sql) -> str:
        minutes = " ".join(f"WHEN '{k}' THEN {v}" for k, v in SCHEDULED_MINUTES.items())
        return f"""
SELECT l.line_id, l.line_name, l.product_family, l.rated_units_per_hour, l.shift_pattern,
       CASE l.shift_pattern {minutes} END AS scheduled_minutes_per_day, l.commissioned_date,
       l.site_id, si.site_name, si.country, si.region
FROM {s.ref('bronze_production_lines')} l
JOIN {s.ref('silver_sites')} si ON si.site_id = l.site_id"""

    def products_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT sku, product_name, product_family, unit_of_measure, standard_cost, list_price, currency,
       {d.money('list_price - standard_cost')} AS unit_margin, {d.pct('list_price - standard_cost', 'list_price')} AS margin_pct,
       weight_kg, is_active
FROM {s.ref('bronze_products')}"""

    def work_orders_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  w.work_order_id,
  w.line_id,
  l.line_name,
  w.sku,
  pr.product_name,
  pr.product_family,
  w.scheduled_date,
  w.shift_name,
  w.started_at,
  w.completed_at,
  UPPER(TRIM(w.work_order_status)) AS work_order_status,
  w.planned_qty,
  w.produced_qty,
  w.scrap_qty,
  w.produced_qty - w.scrap_qty AS good_qty,
  {d.pct('w.scrap_qty', 'w.produced_qty')} AS scrap_rate_pct,
  {d.pct('w.produced_qty', 'w.planned_qty')} AS attainment_pct,
  {d.money('w.scrap_qty * pr.standard_cost')} AS scrap_cost_aud,
  w.supervisor_employee_id,
  l.site_id,
  l.site_name,
  l.country,
  l.region
FROM {s.ref('bronze_work_orders')} w
JOIN {s.ref('silver_production_lines')} l ON l.line_id = w.line_id
JOIN {s.ref('silver_products')} pr ON pr.sku = w.sku"""

    def downtime_sql(s: Sql) -> str:
        return f"""
WITH deduplicated AS (
  -- The MES re-sends some events: keep the latest copy of each.
  SELECT e.*, ROW_NUMBER() OVER (PARTITION BY e.event_id ORDER BY e._batch_id DESC) AS rn
  FROM {s.ref('bronze_downtime_events')} e
)
SELECT e.event_id, e.line_id, l.line_name, e.work_order_id, e.started_at, CAST(e.started_at AS DATE) AS event_date,
       e.duration_minutes, e.reason_code,
       CASE WHEN e.reason_code IN ('PLANNED_MAINTENANCE', 'CHANGEOVER') THEN TRUE ELSE FALSE END AS is_planned,
       e.operator_comment, e.reported_by_employee_id, l.site_id, l.site_name, l.country, l.region
FROM deduplicated e
JOIN {s.ref('silver_production_lines')} l ON l.line_id = e.line_id
WHERE e.rn = 1"""

    def incidents_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT i.incident_id, i.site_id, si.site_name, i.occurred_at, CAST(i.occurred_at AS DATE) AS incident_date,
       {d.month_start('CAST(i.occurred_at AS DATE)')} AS incident_month, i.incident_type, i.severity, i.injured_employee_id,
       i.injury_type, i.body_part, i.treatment, i.lost_time_days,
       CASE WHEN i.lost_time_days > 0 THEN TRUE ELSE FALSE END AS is_lost_time_injury, i.workers_comp_claim_number,
       i.description, i.reported_by_employee_id, si.country, si.region
FROM {s.ref('bronze_safety_incidents')} i
JOIN {s.ref('silver_sites')} si ON si.site_id = i.site_id"""

    return [
        Derived("silver_sites", "Sites with region.", sites_sql),
        Derived("silver_production_lines", "Lines with site, region and scheduled minutes per day.", lines_sql),
        Derived("silver_products", "Products with unit margin and margin percentage.", products_sql),
        Derived("silver_work_orders", "Work orders with clean status, product, good quantity, scrap rate, attainment, AUD scrap cost and the site's region.", work_orders_sql),
        Derived("silver_downtime_events", "Downtime without duplicates, with planned flag, line, site and region.", downtime_sql),
        Derived("silver_safety_incidents", "Safety incidents with month, lost time flag, site and region.", incidents_sql),
    ]


def gold() -> list[Derived]:
    def line_daily_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH line_output AS (
  SELECT line_id, scheduled_date, COUNT(*) AS work_orders, SUM(planned_qty) AS planned_qty, SUM(produced_qty) AS produced_qty,
         SUM(good_qty) AS good_qty, SUM(scrap_qty) AS scrap_qty, SUM(scrap_cost_aud) AS scrap_cost_aud
  FROM {s.ref('silver_work_orders')}
  WHERE work_order_status IN ('COMPLETED', 'IN_PROGRESS')
  GROUP BY line_id, scheduled_date
),
stoppages AS (
  SELECT line_id, event_date, SUM(duration_minutes) AS downtime_minutes,
         SUM(CASE WHEN NOT is_planned THEN duration_minutes ELSE 0 END) AS unplanned_downtime_minutes
  FROM {s.ref('silver_downtime_events')}
  GROUP BY line_id, event_date
)
SELECT
  o.scheduled_date AS production_date,
  l.site_id,
  l.site_name,
  o.line_id,
  l.line_name,
  l.product_family,
  o.work_orders,
  o.planned_qty,
  o.produced_qty,
  o.good_qty,
  o.scrap_qty,
  {d.pct('o.scrap_qty', 'o.produced_qty')} AS scrap_rate_pct,
  o.scrap_cost_aud,
  COALESCE(st.downtime_minutes, 0) AS downtime_minutes,
  COALESCE(st.unplanned_downtime_minutes, 0) AS unplanned_downtime_minutes,
  {d.pct(f'GREATEST(l.scheduled_minutes_per_day - COALESCE(st.downtime_minutes, 0), 0)', 'l.scheduled_minutes_per_day')} AS availability_pct,
  l.country,
  l.region
FROM line_output o
JOIN {s.ref('silver_production_lines')} l ON l.line_id = o.line_id
LEFT JOIN stoppages st ON st.line_id = o.line_id AND st.event_date = o.scheduled_date"""

    def downtime_pareto_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH ranked AS (
  SELECT e.*, {d.month_start('e.event_date')} AS event_month,
         ROW_NUMBER() OVER (PARTITION BY {d.month_start('e.event_date')}, e.line_id, e.reason_code ORDER BY e.started_at DESC) AS rn
  FROM {s.ref('silver_downtime_events')} e
)
SELECT
  event_month,
  site_name,
  line_id,
  line_name,
  reason_code,
  region,
  COUNT(*) AS events,
  SUM(duration_minutes) AS downtime_minutes,
  ROUND(AVG(duration_minutes), 1) AS avg_minutes_per_event,
  MAX(CASE WHEN rn = 1 THEN operator_comment END) AS latest_comment
FROM ranked
GROUP BY 1, 2, 3, 4, 5, 6"""

    def safety_sql(s: Sql) -> str:
        return f"""
SELECT
  incident_month,
  site_id,
  site_name,
  region,
  COUNT(*) AS incidents,
  SUM(CASE WHEN incident_type = 'INJURY' THEN 1 ELSE 0 END) AS injuries,
  SUM(CASE WHEN is_lost_time_injury THEN 1 ELSE 0 END) AS lost_time_injuries,
  SUM(lost_time_days) AS lost_time_days,
  SUM(CASE WHEN incident_type = 'NEAR_MISS' THEN 1 ELSE 0 END) AS near_misses,
  SUM(CASE WHEN severity = 'HIGH' THEN 1 ELSE 0 END) AS high_severity_incidents,
  SUM(CASE WHEN workers_comp_claim_number IS NOT NULL THEN 1 ELSE 0 END) AS workers_comp_claims
FROM {s.ref('silver_safety_incidents')}
GROUP BY 1, 2, 3, 4"""

    return [
        Derived("gold_line_performance_daily", "Output by day and line: work orders, planned, produced, good and scrap quantities, AUD scrap cost, downtime and availability.", line_daily_sql),
        Derived("gold_downtime_pareto", "Downtime by month, line and reason: events, minutes and the latest operator comment.", downtime_pareto_sql),
        Derived("gold_safety_summary", "Safety incidents by month and site: injuries, lost time injuries and days, near misses and workers compensation claims.", safety_sql),
    ]


def schema() -> Schema:
    return Schema(
        "production",
        "Forgeline Production",
        "Production: sites, lines, the product master, work orders, downtime and safety incidents. "
        "Sources: the manufacturing execution system (MES), the ERP and the safety system (SafetyHub).",
        bronze(), silver(), gold(),
    )
