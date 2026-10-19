"""Supply chain: suppliers, purchase orders, customers, sales orders and
inventory from the ERP."""

from __future__ import annotations

from decimal import Decimal

from ... import fake, hr
from ...common import FX_TO_AUD, aud_sql, country_sql, meta_columns, region_sql
from ...model import Col, DaysAgo, Derived, Schema, Sql, Table
from . import COMPANY, PRODUCTS, RAW_COUNTRY, SITES

CURRENCY = {"AU": "AUD", "NZ": "NZD", "SG": "SGD", "GB": "GBP", "US": "USD", "DE": "EUR"}
SUPPLIER_COUNTRIES = {"AU": 55, "NZ": 8, "SG": 7, "GB": 8, "US": 13, "DE": 9}
COMPANY_SUFFIX = {"AU": "Pty Ltd", "NZ": "Ltd", "SG": "Pte Ltd", "GB": "Ltd", "US": "Inc", "DE": "GmbH"}
# German suppliers: fake.py has no German places. 030 23125 xxx is the range
# Germany's Bundesnetzagentur sets aside for fiction.
OTHER_PLACES = {"DE": ("Stuttgart", "+49 30 23125 {}")}
PREFIXES = ("Southern", "Pacific", "Coastal", "Summit", "Ironbark", "Redgum", "Harbour", "Continental", "Allied",
            "Precision", "Apex", "Keystone", "Meridian", "Eastern", "Western", "Northern")
# Supplier category: (name words, materials as (description, unit price range in AUD))
CATEGORIES = {
    "CASTINGS": (("Foundry", "Castings"), (("Pump housing casting", (180, 900)), ("Valve body casting", (40, 260)),
                                            ("Impeller casting", (30, 140)))),
    "STEEL": (("Steel", "Metals"), (("Stainless plate 6 mm, per tonne", (4200, 6500)), ("Mild steel RHS, per length", (90, 240)),
                                    ("Structural beam, per length", (300, 900)))),
    "ELECTRICAL": (("Electrical", "Motors"), (("Electric motor 15 kW", (1200, 2200)), ("Variable speed drive", (900, 1800)),
                                             ("Cable, per 100 m", (150, 400)))),
    "BEARINGS": (("Bearings", "Drives"), (("Bearing 6309", (18, 45)), ("Gearbox", (900, 2600)), ("Coupling", (60, 180)))),
    "SEALS": (("Seals", "Polymers"), (("Mechanical seal", (35, 120)), ("O-ring kit", (5, 20)), ("Valve seat", (8, 30)))),
    "PACKAGING": (("Packaging", "Crates"), (("Export crate", (120, 380)), ("Pallet", (18, 40)))),
    "LOGISTICS": (("Freight", "Logistics"), (("Freight: linehaul", (800, 4500)), ("Freight: sea container", (2800, 7500)))),
}
CATEGORY_WEIGHTS = {"CASTINGS": 16, "STEEL": 16, "ELECTRICAL": 14, "BEARINGS": 14, "SEALS": 14, "PACKAGING": 10, "LOGISTICS": 8}
CUSTOMER_COUNTRIES = {"AU": 65, "NZ": 12, "SG": 5, "GB": 6, "US": 12}
CUSTOMER_PREFIXES = {
    "AU": ("Goldfields", "Riverina", "Pilbara", "Hunter", "Gippsland", "Murray", "Kimberley", "Bowen", "Fraser", "Darling"),
    "NZ": ("Waikato", "Canterbury", "Otago", "Taranaki"), "SG": ("Jurong", "Straits", "Marina"),
    "GB": ("Yorkshire", "Thames", "Pennine", "Severn"), "US": ("Texas", "Gulf Coast", "Lone Star", "Permian"),
}
# Industry: (name words, product families they buy)
INDUSTRIES = {
    "MINING": (("Mining", "Resources", "Minerals"), ("PUMPS", "CONVEYORS", "SPARE_PARTS", "FABRICATION")),
    "WATER_UTILITY": (("Water", "Water Services"), ("PUMPS", "VALVES", "SPARE_PARTS")),
    "AGRICULTURE": (("Irrigation", "Farms", "Agriculture"), ("PUMPS", "VALVES")),
    "FOOD_PROCESSING": (("Foods", "Dairy", "Beverages"), ("PUMPS", "VALVES", "FABRICATION")),
    "OIL_AND_GAS": (("Energy", "Petroleum"), ("VALVES", "PUMPS", "SPARE_PARTS")),
    "CONSTRUCTION": (("Construction", "Civil"), ("CONVEYORS", "FABRICATION", "SPARE_PARTS")),
}
CONTACT_TITLES = ("Maintenance Manager", "Procurement Officer", "Site Engineer", "Operations Manager", "Reliability Engineer")
# Where each product family ships from. US pumps and parts come from Austin, Singapore stock from Tuas.
SHIPS_FROM = {"PUMPS": "S01", "VALVES": "S02", "CONVEYORS": "S03", "FABRICATION": "S04", "SPARE_PARTS": "S06"}
LEAD_DAYS = {"PUMPS": (7, 30), "VALVES": (5, 21), "CONVEYORS": (30, 90), "FABRICATION": (30, 90), "SPARE_PARTS": (2, 10)}
CARRIERS = {"AU": ("Toll", "StarTrack", "TNT"), "NZ": ("Mainfreight",), "SG": ("DHL",), "GB": ("DHL",), "US": ("FedEx", "UPS")}
# Sites stocking each family: plants, warehouses and (for parts) service centres.
STOCKED_AT = {"PUMPS": ("S01", "S05", "S06", "S07", "S08"), "VALVES": ("S02", "S06", "S07", "S08"), "CONVEYORS": ("S03",),
              "FABRICATION": ("S04",), "SPARE_PARTS": ("S01", "S03", "S05", "S06", "S07", "S08", "S09", "S10", "S11")}
META = ("ERP", "erp-0412")

_cache: dict = {}


def _phone(r, country: str) -> str:
    return OTHER_PLACES[country][1].format(fake.digits(r, 3)) if country in OTHER_PLACES else fake.phone(r, country, mobile=False)


def suppliers() -> list[dict]:
    if "suppliers" in _cache:
        return _cache["suppliers"]
    r = fake.rng("forgeline", "supply_chain", "suppliers")
    result, names = [], set()
    while len(result) < 60:
        country = fake.weighted(r, SUPPLIER_COUNTRIES)
        category = fake.weighted(r, CATEGORY_WEIGHTS)
        name = f"{r.choice(PREFIXES)} {r.choice(CATEGORIES[category][0])} {COMPANY_SUFFIX[country]}"
        if name in names:
            continue
        names.add(name)
        first, last = fake.name(r)
        result.append({
            "id": f"SUP{len(result) + 1:04d}", "name": name, "country": country, "category": category,
            "city": OTHER_PLACES[country][0] if country in OTHER_PLACES else r.choice(fake.PLACES[country])[0],
            "contact": f"{first} {last}", "email": f"{first}.{last}@{name.split()[0].lower()}{category.lower()}.example.com".lower(),
            "phone": _phone(r, country), "late_chance": 0.5 if fake.chance(r, 0.15) else 0.1,
        })
    _cache["suppliers"] = result
    return result


def customers() -> list[dict]:
    if "customers" in _cache:
        return _cache["customers"]
    r = fake.rng("forgeline", "supply_chain", "customers")
    account_managers = [s for s in hr.staff_in(COMPANY, "SUPPLY_CHAIN") if s["department"]["department_name"] == "Sales"]
    result, names = [], set()
    while len(result) < 90:
        country = fake.weighted(r, CUSTOMER_COUNTRIES)
        industry = r.choice(list(INDUSTRIES))
        name = f"{r.choice(CUSTOMER_PREFIXES[country])} {r.choice(INDUSTRIES[industry][0])} {COMPANY_SUFFIX[country]}"
        if name in names:
            continue
        names.add(name)
        first, last = fake.name(r)
        result.append({
            "id": f"CUS{len(result) + 1:04d}", "name": name, "country": country, "industry": industry,
            "contact_first": first, "contact_last": last, "title": r.choice(CONTACT_TITLES),
            "email": f"{first}.{last}@{name.split()[0].lower()}{industry.split('_')[0].lower()}.example.com".lower(),
            "phone": fake.phone(r, country), "address": fake.address(r, country),
            "account_manager": r.choice(account_managers)["employee_id"],
        })
    _cache["customers"] = result
    return result


def sales_orders() -> list[dict]:
    """Sales orders for the last six months. Quality uses delivered orders for
    complaints and warranty claims."""
    if "sales_orders" in _cache:
        return _cache["sales_orders"]
    r = fake.rng("forgeline", "supply_chain", "sales_orders")
    result = []
    for i in range(950):
        customer = r.choice(customers())
        family = r.choice(INDUSTRIES[customer["industry"]][1])
        sku = r.choice([p for p in PRODUCTS if p[2] == family])
        price = Decimal(sku[4])
        quantity = 1 if price > 20000 else r.randint(1, 4) if price > 3000 else r.randint(1, 12) if price > 500 else r.randint(5, 80)
        site = SHIPS_FROM[family]
        if customer["country"] == "US" and family in ("PUMPS", "SPARE_PARTS"):
            site = "S05"
        elif customer["country"] == "SG" and family in ("PUMPS", "VALVES", "SPARE_PARTS"):
            site = "S08"
        ordered = r.randint(0, 180)
        lead = r.randint(*LEAD_DAYS[family])
        requested = ordered - lead
        late = fake.chance(r, 0.3 if site == "S02" else 0.12)  # the Geelong valve plant is behind
        actual = lead + r.randint(1, 20) if late else lead - r.randint(0, min(3, lead - 1))
        delivered = ordered - actual
        shipped = delivered + r.randint(1, 5)
        if fake.chance(r, 0.03):
            status = "CANCELLED"
        elif shipped < 0:
            status = "OPEN"
        elif delivered < 0:
            status = "SHIPPED"
        else:
            status = "DELIVERED"
        currency = CURRENCY[customer["country"]]
        result.append({
            "id": f"SO{5000001 + i}", "customer": customer, "sku": sku[0], "family": family, "quantity": quantity,
            "unit_price": (price / Decimal(FX_TO_AUD[currency])).quantize(Decimal("0.01")), "currency": currency,
            "discount": Decimal(r.choice((0, 0, 0, 5, 10, 15))), "ordered": ordered, "requested": requested, "site": site,
            "shipped": shipped if status in ("SHIPPED", "DELIVERED") else None,
            "delivered": delivered if status == "DELIVERED" else None, "status": status,
        })
    _cache["sales_orders"] = result
    return result


def bronze() -> list[Table]:
    m = meta_columns()

    r = fake.rng("forgeline", "supply_chain", "supplier_rows")
    supplier_rows = []
    for s in suppliers():
        country = s["country"]
        supplier_rows.append((
            s["id"], s["name"] + ("  " if fake.chance(r, 0.1) else ""), s["category"], fake.abn(r) if country == "AU" else None,
            None if country == "AU" else fake.digits(r, 9), s["city"], r.choice(RAW_COUNTRY.get(country, (country,))),
            s["contact"], s["email"], s["phone"], fake.bsb(r, r.choice(("062", "033", "083", "013"))) if country == "AU" else None,
            fake.digits(r, 9 if country == "AU" else 10),
            fake.gb_iban(r, r.choice(("BARC", "LOYD", "NWBK"))) if country == "GB"
            else f"DE{fake.digits(r, 20)}" if country == "DE" else None,
            r.choice((30, 30, 45, 60)), fake.chance(r, 0.35), DaysAgo(r.randint(200, 4000)), *META,
        ))

    r = fake.rng("forgeline", "supply_chain", "purchase_orders")
    buyers = [s for s in hr.staff_in(COMPANY, "SUPPLY_CHAIN") if s["department"]["department_name"] == "Procurement"]
    plants = [s for s in SITES if s[2] == "PLANT"]
    po_rows = []
    for i in range(600):
        supplier = r.choice(suppliers())
        material, price_range = r.choice(CATEGORIES[supplier["category"]][1])
        currency = CURRENCY[supplier["country"]]
        price = (fake.money(r, *price_range) / Decimal(FX_TO_AUD[currency])).quantize(Decimal("0.01"))
        quantity = r.randint(1, 10) if price_range[0] >= 1000 else r.randint(5, 60) if price_range[0] >= 100 else r.randint(20, 500)
        ordered = r.randint(0, 240)
        lead = r.randint(7, 21) if supplier["country"] in ("AU", "NZ") else r.randint(28, 70)
        promised = ordered - lead
        received = promised - (r.randint(1, 21) if fake.chance(r, supplier["late_chance"]) else -r.randint(0, 5))
        received = min(received, ordered - 1) if ordered > 0 else received
        if fake.chance(r, 0.03):
            status, received = "CANCELLED", None
        elif received < 0:
            status, received = "OPEN", None
        else:
            status = "PARTIAL" if fake.chance(r, 0.05) else "RECEIVED"
        po_rows.append((
            f"PO{7000001 + i}", supplier["id"], r.choice(plants)[0], material, supplier["category"], quantity, price, currency,
            DaysAgo(ordered), DaysAgo(promised), DaysAgo(received) if received is not None else None,
            r.choice((status, status.title())), r.choice(buyers)["employee_id"], *META,
        ))

    r = fake.rng("forgeline", "supply_chain", "customer_rows")
    customer_rows = []
    for c in customers():
        a = c["address"]
        customer_rows.append((
            c["id"], c["name"], c["industry"], fake.abn(r) if c["country"] == "AU" else None,
            None if c["country"] == "AU" else fake.digits(r, 9), c["contact_first"], c["contact_last"], c["title"],
            c["email"].upper() if fake.chance(r, 0.05) else c["email"], c["phone"], a["address_line"], a["suburb"], a["state"],
            a["postcode"], r.choice(RAW_COUNTRY[c["country"]]), Decimal(r.choice((50, 100, 250, 500, 1000)) * 1000),
            r.choice((30, 30, 45, 60)), c["account_manager"], DaysAgo(r.randint(200, 6000)), *META,
        ))

    r = fake.rng("forgeline", "supply_chain", "sales_order_rows")
    so_rows = []
    for o in sales_orders():
        country = o["customer"]["country"]
        so_rows.append((
            o["id"], o["customer"]["id"], o["sku"], o["quantity"], o["unit_price"], o["discount"], o["currency"], DaysAgo(o["ordered"]),
            DaysAgo(o["requested"]), DaysAgo(o["shipped"]) if o["shipped"] is not None else None,
            DaysAgo(o["delivered"]) if o["delivered"] is not None else None, o["status"], o["site"],
            r.choice(CARRIERS[country]) if o["shipped"] is not None else None, f"PO-{fake.digits(r, 6)}", *META,
        ))

    r = fake.rng("forgeline", "supply_chain", "inventory")
    inventory_rows = []
    for sku, _, family, cost, _, _ in PRODUCTS:
        for site in STOCKED_AT[family]:
            reorder = max(1, int(4000 / cost * r.uniform(2, 6))) if cost < 4000 else r.randint(1, 2)
            safety = max(1, reorder // 2)
            status = fake.weighted(r, {"OK": 72, "LOW": 20, "CRITICAL": 8})
            on_hand = {"OK": r.randint(reorder + 1, reorder * 3 + 2), "LOW": r.randint(safety, reorder),
                       "CRITICAL": r.randint(0, max(safety - 1, 0))}[status]
            inventory_rows.append((
                DaysAgo(0), sku, site, on_hand, r.randint(0, on_hand // 2), reorder, safety, DaysAgo(r.randint(1, 90)), *META,
            ))

    return [
        Table("bronze_suppliers", "Suppliers of castings, steel, electrical parts, bearings, seals, packaging and freight, with bank details for payment.", [
            Col("supplier_id", "string"), Col("supplier_name", "string"), Col("category", "string"),
            Col("abn", "string", "Australian Business Number"), Col("registration_number", "string", "Company registration number outside Australia"),
            Col("city", "string"), Col("country", "string", "Raw country as entered: AU, AUS, Australia..."),
            Col("contact_name", "string", "Person name"), Col("contact_email", "string", "PII: email"),
            Col("contact_phone", "string", "PII: phone number"), Col("bank_bsb", "string", "Financial: BSB"),
            Col("bank_account_number", "string", "Financial: account number"), Col("iban", "string", "Financial: IBAN"),
            Col("payment_terms_days", "int"), Col("is_preferred", "bool"), Col("onboarded_date", "date"), *m], supplier_rows),
        Table("bronze_purchase_orders", "Purchase orders to suppliers for the last eight months. received_date is empty until goods arrive.", [
            Col("po_id", "string"), Col("supplier_id", "string"), Col("site_id", "string", "The receiving plant"),
            Col("material_description", "string"), Col("category", "string"), Col("quantity", "int"),
            Col("unit_price", "decimal(12,2)", "Commercially sensitive"), Col("currency", "string"), Col("order_date", "date"),
            Col("promised_date", "date"), Col("received_date", "date"), Col("po_status", "string"),
            Col("buyer_employee_id", "string", "Matches employee_id in the HR data"), *m], po_rows),
        Table("bronze_customers", "Business customers: mines, water utilities, farms, food processors, energy and construction companies.", [
            Col("customer_id", "string"), Col("company_name", "string"), Col("industry", "string"),
            Col("abn", "string", "Australian Business Number"), Col("registration_number", "string"),
            Col("contact_first_name", "string", "Person name"), Col("contact_last_name", "string", "Person name"),
            Col("contact_title", "string"), Col("contact_email", "string", "PII: email"), Col("contact_phone", "string", "PII: phone number"),
            Col("address_line", "string"), Col("suburb", "string"), Col("state", "string"), Col("postcode", "string"),
            Col("country", "string", "Raw country as entered: AU, AUS, Australia..."), Col("credit_limit", "decimal(12,2)"),
            Col("payment_terms_days", "int"), Col("account_manager_employee_id", "string", "Matches employee_id in the HR data"),
            Col("customer_since", "date"), *m], customer_rows),
        Table("bronze_sales_orders", "Sales orders for the last six months, one product per order, priced in the customer's currency.", [
            Col("order_id", "string"), Col("customer_id", "string"), Col("sku", "string"), Col("quantity", "int"),
            Col("unit_price", "decimal(12,2)"), Col("discount_pct", "decimal(5,2)"), Col("currency", "string"),
            Col("order_date", "date"), Col("requested_date", "date"), Col("shipped_date", "date"), Col("delivered_date", "date"),
            Col("order_status", "string"), Col("ship_from_site_id", "string"), Col("carrier", "string"),
            Col("customer_po_number", "string"), *m], so_rows),
        Table("bronze_inventory", "Today's stock on hand by product and site, with reorder point and safety stock.", [
            Col("snapshot_date", "date"), Col("sku", "string"), Col("site_id", "string"), Col("on_hand_qty", "int"),
            Col("allocated_qty", "int"), Col("reorder_point", "int"), Col("safety_stock", "int"), Col("last_counted_date", "date"),
            *m], inventory_rows),
    ]


def silver() -> list[Derived]:
    def suppliers_sql(s: Sql) -> str:
        return f"""
WITH base AS (
  SELECT
    su.supplier_id,
    TRIM(su.supplier_name) AS supplier_name,
    su.category,
    REGEXP_REPLACE(su.abn, '[^0-9]', '') AS abn,
    su.registration_number,
    su.city,
    {country_sql('su.country')} AS country,
    su.contact_name,
    LOWER(TRIM(su.contact_email)) AS contact_email,
    su.contact_phone,
    su.bank_bsb,
    su.bank_account_number,
    su.iban,
    su.payment_terms_days,
    su.is_preferred,
    su.onboarded_date
  FROM {s.ref('bronze_suppliers')} su
)
SELECT base.*, {region_sql('base.country')} AS region
FROM base"""

    def purchase_orders_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH base AS (
  SELECT po.*, UPPER(TRIM(po.po_status)) AS clean_status
  FROM {s.ref('bronze_purchase_orders')} po
)
SELECT
  po.po_id,
  po.supplier_id,
  su.supplier_name,
  su.country AS supplier_country,
  po.site_id,
  si.site_name,
  po.material_description,
  po.category,
  po.quantity,
  po.unit_price,
  po.currency,
  {d.money('po.quantity * po.unit_price')} AS order_amount,
  {aud_sql('po.quantity * po.unit_price', 'po.currency', d.money)} AS order_amount_aud,
  po.order_date,
  {d.month_start('po.order_date')} AS order_month,
  po.promised_date,
  po.received_date,
  po.clean_status AS po_status,
  CASE WHEN po.clean_status = 'OPEN' THEN TRUE ELSE FALSE END AS is_open,
  CASE WHEN po.received_date IS NOT NULL THEN {d.days_between('po.promised_date', 'po.received_date')}
       WHEN po.clean_status = 'OPEN' AND po.promised_date < {d.today} THEN {d.days_between('po.promised_date', d.today)} END AS days_late,
  CASE WHEN po.received_date IS NOT NULL AND po.received_date <= po.promised_date THEN TRUE ELSE FALSE END AS is_on_time,
  po.buyer_employee_id,
  si.country,
  si.region
FROM base po
JOIN {s.ref('silver_suppliers')} su ON su.supplier_id = po.supplier_id
JOIN {s.ref('production.silver_sites')} si ON si.site_id = po.site_id"""

    def customers_sql(s: Sql) -> str:
        return f"""
WITH base AS (
  SELECT
    c.customer_id,
    TRIM(c.company_name) AS customer_name,
    c.industry,
    REGEXP_REPLACE(c.abn, '[^0-9]', '') AS abn,
    c.registration_number,
    c.contact_first_name,
    c.contact_last_name,
    c.contact_title,
    LOWER(TRIM(c.contact_email)) AS contact_email,
    c.contact_phone,
    c.address_line,
    c.suburb,
    c.state,
    c.postcode,
    {country_sql('c.country')} AS country,
    c.credit_limit,
    c.payment_terms_days,
    c.account_manager_employee_id,
    c.customer_since
  FROM {s.ref('bronze_customers')} c
)
SELECT base.*, {region_sql('base.country')} AS region
FROM base"""

    def sales_orders_sql(s: Sql) -> str:
        d = s.d
        amount = "so.quantity * so.unit_price * (100 - so.discount_pct) / 100"
        return f"""
SELECT
  so.order_id,
  so.customer_id,
  c.customer_name,
  c.industry,
  so.sku,
  pr.product_name,
  pr.product_family,
  so.quantity,
  so.unit_price,
  so.discount_pct,
  so.currency,
  {d.money(amount)} AS order_amount,
  {aud_sql(amount, 'so.currency', d.money)} AS order_amount_aud,
  so.order_date,
  {d.month_start('so.order_date')} AS order_month,
  so.requested_date,
  so.shipped_date,
  so.delivered_date,
  so.order_status,
  CASE WHEN so.delivered_date IS NOT NULL AND so.delivered_date <= so.requested_date THEN TRUE ELSE FALSE END AS is_on_time,
  CASE WHEN so.delivered_date IS NOT NULL THEN GREATEST({d.days_between('so.requested_date', 'so.delivered_date')}, 0) END AS days_late,
  so.ship_from_site_id,
  si.site_name AS ship_from_site_name,
  so.carrier,
  so.customer_po_number,
  c.country,
  c.region
FROM {s.ref('bronze_sales_orders')} so
JOIN {s.ref('silver_customers')} c ON c.customer_id = so.customer_id
JOIN {s.ref('production.silver_products')} pr ON pr.sku = so.sku
JOIN {s.ref('production.silver_sites')} si ON si.site_id = so.ship_from_site_id"""

    def inventory_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  i.snapshot_date,
  i.sku,
  pr.product_name,
  pr.product_family,
  i.site_id,
  si.site_name,
  si.site_type,
  i.on_hand_qty,
  i.allocated_qty,
  i.on_hand_qty - i.allocated_qty AS available_qty,
  i.reorder_point,
  i.safety_stock,
  CASE WHEN i.on_hand_qty < i.safety_stock THEN 'BELOW_SAFETY_STOCK'
       WHEN i.on_hand_qty <= i.reorder_point THEN 'BELOW_REORDER_POINT' ELSE 'OK' END AS stock_status,
  {d.money('i.on_hand_qty * pr.standard_cost')} AS stock_value_aud,
  i.last_counted_date,
  si.country,
  si.region
FROM {s.ref('bronze_inventory')} i
JOIN {s.ref('production.silver_products')} pr ON pr.sku = i.sku
JOIN {s.ref('production.silver_sites')} si ON si.site_id = i.site_id"""

    return [
        Derived("silver_suppliers", "Suppliers with trimmed names, ABN digits only, ISO country and region.", suppliers_sql),
        Derived("silver_purchase_orders", "Purchase orders with supplier, receiving site, AUD amounts, days late and on-time flag. region is the receiving site's.", purchase_orders_sql),
        Derived("silver_customers", "Customers with trimmed names, ABN digits only, ISO country and region.", customers_sql),
        Derived("silver_sales_orders", "Sales orders with customer, product, discounted and AUD amounts, on-time flag and the customer's region.", sales_orders_sql),
        Derived("silver_inventory", "Stock by product and site with available quantity, stock status and AUD stock value.", inventory_sql),
    ]


def gold() -> list[Derived]:
    def supplier_performance_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH orders AS (
  SELECT
    supplier_id,
    COUNT(*) AS purchase_orders_6_months,
    SUM(order_amount_aud) AS spend_6_months_aud,
    SUM(CASE WHEN received_date IS NOT NULL THEN 1 ELSE 0 END) AS received_orders,
    SUM(CASE WHEN is_on_time THEN 1 ELSE 0 END) AS on_time_orders,
    ROUND(AVG(CASE WHEN days_late > 0 THEN days_late END), 1) AS avg_days_late_when_late,
    SUM(CASE WHEN is_open THEN 1 ELSE 0 END) AS open_orders,
    SUM(CASE WHEN is_open AND days_late > 0 THEN 1 ELSE 0 END) AS overdue_open_orders
  FROM {s.ref('silver_purchase_orders')}
  WHERE order_date >= {d.add_days(d.today, -183)} AND po_status <> 'CANCELLED'
  GROUP BY supplier_id
)
SELECT
  su.supplier_id,
  su.supplier_name,
  su.category,
  su.is_preferred,
  COALESCE(o.purchase_orders_6_months, 0) AS purchase_orders_6_months,
  COALESCE(o.spend_6_months_aud, 0) AS spend_6_months_aud,
  COALESCE(o.received_orders, 0) AS received_orders,
  {d.pct('o.on_time_orders', 'o.received_orders')} AS on_time_pct,
  o.avg_days_late_when_late,
  COALESCE(o.open_orders, 0) AS open_orders,
  COALESCE(o.overdue_open_orders, 0) AS overdue_open_orders,
  su.country,
  su.region
FROM {s.ref('silver_suppliers')} su
LEFT JOIN orders o ON o.supplier_id = su.supplier_id"""

    def sales_daily_sql(s: Sql) -> str:
        return f"""
SELECT
  order_date,
  product_family,
  region,
  COUNT(*) AS orders,
  COUNT(DISTINCT customer_id) AS customers,
  SUM(quantity) AS units,
  SUM(order_amount_aud) AS revenue_aud,
  SUM(CASE WHEN order_status IN ('OPEN', 'SHIPPED') THEN 1 ELSE 0 END) AS orders_not_yet_delivered
FROM {s.ref('silver_sales_orders')}
WHERE order_status <> 'CANCELLED'
GROUP BY 1, 2, 3"""

    def inventory_position_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH demand AS (
  SELECT
    sku,
    ship_from_site_id AS site_id,
    SUM(CASE WHEN order_status = 'OPEN' THEN quantity ELSE 0 END) AS open_order_qty,
    SUM(CASE WHEN shipped_date >= {d.add_days(d.today, -90)} THEN quantity ELSE 0 END) AS shipped_90_days_qty
  FROM {s.ref('silver_sales_orders')}
  GROUP BY sku, ship_from_site_id
)
SELECT
  i.sku,
  i.product_name,
  i.product_family,
  i.site_id,
  i.site_name,
  i.on_hand_qty,
  i.allocated_qty,
  i.available_qty,
  i.reorder_point,
  i.safety_stock,
  i.stock_status,
  i.stock_value_aud,
  COALESCE(dm.open_order_qty, 0) AS open_order_qty,
  COALESCE(dm.shipped_90_days_qty, 0) AS shipped_90_days_qty,
  ROUND(CAST(i.available_qty AS DECIMAL(12,1)) * 90 / NULLIF(dm.shipped_90_days_qty, 0), 1) AS days_of_cover,
  i.country,
  i.region
FROM {s.ref('silver_inventory')} i
LEFT JOIN demand dm ON dm.sku = i.sku AND dm.site_id = i.site_id"""

    return [
        Derived("gold_supplier_performance", "One row per supplier: purchase orders and AUD spend in the last six months, on-time delivery and open and overdue orders.", supplier_performance_sql),
        Derived("gold_sales_daily", "Sales orders by day, product family and customer region: orders, customers, units and AUD revenue.", sales_daily_sql),
        Derived("gold_inventory_position", "Stock by product and site with stock status, open order demand, units shipped in 90 days and days of cover.", inventory_position_sql),
    ]


def schema() -> Schema:
    return Schema(
        "supply_chain",
        "Forgeline Supply Chain",
        "Supply chain: suppliers, purchase orders, customers, sales orders and inventory. Source: the ERP.",
        bronze(), silver(), gold(),
    )
