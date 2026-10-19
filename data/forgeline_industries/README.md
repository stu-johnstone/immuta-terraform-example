# Forgeline Industries

A fictional manufacturer of industrial pumps, valves, conveyors and custom
fabrication, headquartered in Adelaide, with plants in Geelong, Brisbane,
Auckland and Austin, warehouses and service centres. It has three
businesses: **production**, **supply chain** and **quality**.

| File | Platform | Contains |
|---|---|---|
| [`snowflake/forgeline_industries.sql`](snowflake/forgeline_industries.sql) | Snowflake | Your database: schemas `production`, `supply_chain`, `quality` |
| [`redshift/forgeline_hr.sql`](redshift/forgeline_hr.sql) | Redshift | Schema `forgeline` in database `hr` |
| [`bigquery/forgeline_marketing.sql`](bigquery/forgeline_marketing.sql) | BigQuery | Dataset `forgeline_marketing` |

See the [data README](../README.md) for how to run the files, the medallion
layers and regions.

## How the data connects

- `sku` links products across all three schemas; `site_id` links plants,
  warehouses and service centres.
- Inspections are of production work orders (`work_order_id`); complaints
  and warranty claims are about sales orders (`order_id`); non-conformance
  reports point to a work order, a supplier or a complaint.
- Valve Line 2 (`L05`) at the Geelong plant has a worn press: more
  breakdowns, scrap and failed inspections, and Geelong valves are delivered
  late and draw more complaints. The Welding Cell (`L12`) has more weld
  defects.
- Staff IDs in work orders, downtime, safety incidents, purchase orders,
  customers and quality records match `employee_id` in the HR data on
  Redshift, and operator comments and incident reports name them.
- Every silver and gold table has `region` (`APAC`, `EMEA`, `AMER`) and
  `country`. For production and purchasing it is the site's region; for
  sales, complaints and warranty it is the customer's.

## Production (`production`)

Sources: the manufacturing execution system (MES), the ERP product master
and the safety system (SafetyHub).

| Bronze table | Rows | What it holds |
|---|---|---|
| `bronze_sites` | 11 | Plants, warehouses and service centres in Australia, New Zealand, Singapore, the UK and the US |
| `bronze_production_lines` | 15 | Lines, with rated output and shift pattern |
| `bronze_products` | 26 | Products, with **standard cost** and list price |
| `bronze_work_orders` | 801 | Four months of work orders and the next ten days: planned, produced and scrap quantities |
| `bronze_downtime_events` | 437 | Stoppages with reason and **operator comments naming staff, phone numbers and staff illnesses**; 10 are duplicates |
| `bronze_safety_incidents` | 90 | Injuries, near misses, damage and spills: **injured worker, injury, treatment, workers compensation claim and medical history** |

Silver cleans these up (one row per event, clean statuses, good quantity,
scrap rate, attainment, AUD scrap cost, scheduled minutes per day).

| Gold table | One row per |
|---|---|
| `gold_line_performance_daily` | Day and line: output, scrap and scrap cost, downtime and availability |
| `gold_downtime_pareto` | Month, line and reason: events, minutes and the latest operator comment |
| `gold_safety_summary` | Month and site: injuries, lost time injuries and days, near misses and workers compensation claims |

## Supply chain (`supply_chain`)

Source: the ERP.

| Bronze table | Rows | What it holds |
|---|---|---|
| `bronze_suppliers` | 60 | Suppliers: **ABN**, contacts and **bank details (BSB, account number, IBAN)** |
| `bronze_purchase_orders` | 600 | Eight months of purchase orders, with promised and received dates |
| `bronze_customers` | 90 | Business customers: **ABN**, contact name, email and phone, credit limit |
| `bronze_sales_orders` | 950 | Six months of sales orders, in the customer's currency, with requested and delivered dates |
| `bronze_inventory` | 116 | Today's stock by product and site, with reorder point and safety stock |

| Gold table | One row per |
|---|---|
| `gold_supplier_performance` | Supplier: purchase orders and spend in the last six months, on-time delivery, open and overdue orders |
| `gold_sales_daily` | Day, product family and region: orders, customers, units and revenue |
| `gold_inventory_position` | Product and site: stock, status, open order demand and days of cover |

## Quality (`quality`)

Source: the quality management system (QMS).

| Bronze table | Rows | What it holds |
|---|---|---|
| `bronze_inspections` | 600 | Final and first article inspections; `result` is entered by hand (`PASS`, `Pass`, `pass`) |
| `bronze_defects` | 112 | Defects with severity and disposition, and inspector notes |
| `bronze_non_conformances` | 100 | NCRs from inspections, suppliers and complaints, with root cause, cost and corrective action |
| `bronze_customer_complaints` | 110 | Complaints: **customer contacts and free text with names, phones, addresses and injuries** |
| `bronze_warranty_claims` | 130 | Warranty claims with serial number, failure mode and amounts |

| Gold table | One row per |
|---|---|
| `gold_first_pass_yield` | Month, site, line and product family: first pass yield and defects per 100 units |
| `gold_complaint_overview` | Complaint: customer, product, severity, status, days open, warranty claims, NCR and the complaint text |
| `gold_cost_of_quality` | Month and site: scrap, NCR and warranty cost |

## HR (`hr.forgeline` on Redshift)

The same structure for every company (see the
[Harbourstone README](../harbourstone_financial/README.md#hr-hrharbourstone-on-redshift)).
230 employees across 12 departments, including plant operations,
maintenance, procurement and quality.

## Marketing (`forgeline_marketing` on BigQuery)

The same structure for every company: web sessions and events, campaigns,
ad spend, leads with **free-text messages**, email sends and consent history,
for pumps, valves, conveyors, fabrication, spare parts and field service.

## Immuta demo ideas

- **Discovery and classification**: less personal data than the other
  companies, but ABNs, BSBs, IBANs, emails and phones are present, and
  health information hides in incident reports, downtime comments and
  complaints.
- **Masking**: mask `bank_account_number`, `iban` and `bank_bsb`; hide
  `standard_cost` and purchase `unit_price` (commercially sensitive) from
  sales; redact names and phone numbers in `operator_comment`, `description`
  and `complaint_text` with a regex.
- **Row-level security**: limit every table to the user's `Region`. The
  Austin plant and UK service centre (and US and UK customers) make the
  effect visible.
- **Purpose and sensitivity**: restrict `bronze_safety_incidents` (injuries
  and workers compensation) to health and safety; supplier bank details to
  finance.
- **Lineage of trust**: policies on bronze columns should carry through to
  silver and gold.

## Sample questions for AI

Each question can be answered from the gold table shown.

**Production**

- Which line has the worst scrap rate and availability this month, and why?
  (`gold_line_performance_daily`, `gold_downtime_pareto`)
- What are the top downtime reasons by plant over the last three months?
  (`gold_downtime_pareto`)
- How many lost time injuries have there been in the last 12 months, by site?
  (`gold_safety_summary`)

**Supply chain**

- Which suppliers deliver late most often, and how much do we spend with
  them? (`gold_supplier_performance`)
- What was revenue by product family and region last month?
  (`gold_sales_daily`)
- Which products are below safety stock, and how many days of cover do we
  have? (`gold_inventory_position`)

**Quality**

- What is first pass yield by line, and which line is worst?
  (`gold_first_pass_yield`)
- Summarise the open critical complaints and whether they have an NCR.
  (`gold_complaint_overview`)
- What is the cost of quality by plant over the last six months?
  (`gold_cost_of_quality`)
