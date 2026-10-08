# Harbourstone Financial Group

A fictional bank and general insurer headquartered in Sydney, with branches
across Australia and in Auckland, Singapore and London. It has three
businesses: **retail banking**, **commercial banking** and **general (P&C)
insurance**.

| File | Platform | Contains |
|---|---|---|
| [`databricks/harbourstone_financial.sql`](databricks/harbourstone_financial.sql) | Databricks | Your catalog (for example `harbourstone`): schemas `retail_banking`, `commercial_banking`, `insurance` |
| [`redshift/harbourstone_hr.sql`](redshift/harbourstone_hr.sql) | Redshift | Schema `harbourstone` in database `hr` |
| [`bigquery/harbourstone_marketing.sql`](bigquery/harbourstone_marketing.sql) | BigQuery | Dataset `harbourstone_marketing` |

See the [data README](../README.md) for how to run the files, the medallion
layers and regions.

## How the data connects

- `customer_id` links all retail banking tables.
- `bank_customer_id` in insurance links about 90 policyholders to their
  retail banking record (cross-sold customers).
- Staff IDs in CRM notes (`staff_employee_id`), claims (`assessor_employee_id`)
  and commercial lending (`rm_employee_id`, `analyst_employee_id`) match
  `employee_id` in the HR data on Redshift: one person, two platforms.
- Every silver and gold table has `region` (`APAC`, `EMEA`, `AMER`) and
  `country`.

## Retail banking (`retail_banking`)

Sources: core banking (CBS), card management, lending, CRM, a KYC vendor and
the anti-money laundering (AML) engine.

| Bronze table | Rows | What it holds |
|---|---|---|
| `bronze_branches` | 18 | Branches, including Auckland, Singapore, London and the digital branch |
| `bronze_customers` | 250 | Customers: name, date of birth, email, mobile, **tax file number** |
| `bronze_customer_addresses` | 340 | Current and previous addresses |
| `bronze_kyc_documents` | 297 | **Passport, driver licence and Medicare numbers** |
| `bronze_accounts` | 455 | Everyday, savings and term deposit accounts: **BSB, account number, IBAN** |
| `bronze_transactions` | 1010 | 120 days of transactions, including today; 10 are duplicates |
| `bronze_cards` | 286 | Debit and credit cards: **card numbers** and expiry |
| `bronze_home_loans` | 100 | Home loans with property value, balance and arrears |
| `bronze_crm_interactions` | 300 | Contact notes: **free text with card digits, addresses, phone numbers and dates of birth** |
| `bronze_complaints` | 110 | Complaints in the customer's words |
| `bronze_aml_alerts` | 80 | AML alerts, including a structuring pattern, with analyst notes |

Silver cleans these up (one row per transaction, ISO countries, ages and age
bands, AUD amounts, loan-to-value, arrears buckets, days open).

| Gold table | One row per |
|---|---|
| `gold_daily_deposits` | Day and branch: deposits in AUD, split into cash and salary |
| `gold_customer_360` | Customer: balances, cards, home loan, complaints, AML alerts and the last contact note |
| `gold_complaint_themes` | Month, category and region, with resolution time, compensation and the latest example |
| `gold_aml_overview` | Day, rule, risk level, status and region |
| `gold_home_loan_portfolio` | Region, state, rate type and arrears bucket, with LVR |

## Commercial banking (`commercial_banking`)

Source: the commercial lending system (LoanIQ). Each business has a risk
grade from 1 (strong) to 10 (default); higher grades come with more arrears,
covenant breaches and more worrying analyst commentary.

| Bronze table | Rows | What it holds |
|---|---|---|
| `bronze_relationship_managers` | 23 | Relationship managers (from HR) |
| `bronze_business_customers` | 100 | Businesses: **ABN** or other registration number, industry, revenue |
| `bronze_business_contacts` | 200 | Directors and beneficial owners: date of birth, contact details, **politically exposed** flag |
| `bronze_facilities` | 174 | Term loans, overdrafts, equipment, property and trade finance |
| `bronze_collateral` | 135 | Security held, with valuations and guarantor names |
| `bronze_covenants` | 244 | Covenant tests for the last two quarters |
| `bronze_repayments` | 627 | Six months of scheduled repayments, paid, late or missed |
| `bronze_credit_reviews` | 200 | Risk grade, probability of default and **analyst commentary** |

| Gold table | One row per |
|---|---|
| `gold_risk_profile` | Borrower: exposure, utilisation, collateral cover, risk grade and band, breaches, arrears and the latest analyst commentary |
| `gold_portfolio_by_industry` | Industry and region: exposure, average grade, high-risk borrowers, breaches and arrears |
| `gold_arrears_monthly` | Month, facility type and region: repayments due, paid, late and missed |

## Insurance (`insurance`)

Source: the policy and claims system (Guidewire). Motor and home cover in
Australia, New Zealand and Singapore.

| Bronze table | Rows | What it holds |
|---|---|---|
| `bronze_policyholders` | 400 | Policyholders: contact details, **driver licence number** |
| `bronze_policies` | 650 | Motor comprehensive and third party, home building, contents and landlord |
| `bronze_vehicles` | 341 | Insured vehicles: **VIN** and registration |
| `bronze_properties` | 309 | Insured properties with flood and bushfire zone flags |
| `bronze_claims` | 110 | Claims by peril, with amounts and status |
| `bronze_claim_notes` | 214 | **File notes naming third parties, licence numbers, addresses and injuries** |
| `bronze_claim_payments` | 85 | Payments: **payee BSB and account number** |
| `bronze_fraud_flags` | 36 | Fraud indicators and why the claim was flagged |

| Gold table | One row per |
|---|---|
| `gold_loss_ratio` | Product and region: earned premium, claims incurred and loss ratio for the last 12 months |
| `gold_claims_overview` | Claim: status, amounts, fraud flags and the latest file note |
| `gold_catastrophe_exposure` | State and hazard zone: in-force home cover and weather claims |

## HR (`hr.harbourstone` on Redshift)

The same structure for every company. 240 employees across 12 departments.

| Bronze table | What it holds |
|---|---|
| `bronze_departments` | Departments and business units |
| `bronze_employees` | **Tax ID (TFN, IRD, NRIC or NI number), salary bank account**, home address, date of birth, gender, termination reason |
| `bronze_compensation` | Salary history |
| `bronze_payroll` | Last four pay runs |
| `bronze_leave_requests` | Leave, with **reasons that can include health information** |
| `bronze_performance_reviews` | Ratings and the manager's written review |
| `bronze_emergency_contacts` | Next of kin |

Gold: `gold_headcount`, `gold_pay_equity`, `gold_leave_summary`,
`gold_performance_summary`.

## Marketing (`harbourstone_marketing` on BigQuery)

The same structure for every company: GA4-style web sessions and events
(with a raw JSON `event_params` column), campaigns, ad spend, leads with
**free-text messages**, email sends and consent history.

Gold: `gold_campaign_performance`, `gold_funnel_daily`,
`gold_channel_performance`.

## Immuta demo ideas

- **Discovery and classification**: tax file numbers, passport and licence
  numbers, card numbers, BSBs and IBANs, emails, phones and IP addresses are
  all present, in clean columns and inside free text.
- **Masking**: show the last four digits of `card_number`; hash
  `tax_file_number`; round `date_of_birth` to the year; redact phone numbers
  and emails in `notes`, `note_text` and `message` with a regex.
- **Row-level security**: limit every table to the user's `Region`. London
  (EMEA) and US-based (AMER) customers make the effect visible.
- **Purpose and sensitivity**: restrict `bronze_aml_alerts` and
  `is_politically_exposed` to financial crime; HR leave reasons and
  performance reviews to People and Culture.
- **Frameworks**: the HR framework tags employee names across every
  company's HR schema.
- **Lineage of trust**: the same customer appears in bronze, silver and gold;
  policies on bronze columns should carry through to the derived tables.

## Sample questions for AI

Each question can be answered from the gold table shown.

**Retail banking**

- What were total deposits today, and which branch took the most?
  (`gold_daily_deposits`)
- How much cash was deposited at branches in the last 7 days, by region?
  (`gold_daily_deposits`)
- Which customers have open AML alerts and also an open complaint?
  (`gold_customer_360`)
- What were the main complaint themes over the last three months, and how
  long are they taking to resolve? (`gold_complaint_themes`)
- How many structuring alerts are still under investigation, and what did
  the analysts note? (`gold_aml_overview`, `silver_aml_alerts`)
- What share of home loans is more than 30 days in arrears, by state, and
  what is their average LVR? (`gold_home_loan_portfolio`)

**Commercial banking**

- What is the risk profile of the commercial lending book by industry?
  (`gold_portfolio_by_industry`)
- Which borrowers are on the watchlist, how much do we have drawn with them,
  and what did the analyst say? (`gold_risk_profile`)
- Which industries have the most covenant breaches in the last six months?
  (`gold_portfolio_by_industry`)
- Which high-risk borrowers have collateral cover below 1x?
  (`gold_risk_profile`)
- How have missed repayments trended month by month?
  (`gold_arrears_monthly`)

**Insurance**

- What is the loss ratio by product over the last 12 months, and why is
  the worst one so high? (`gold_loss_ratio`, `gold_claims_overview`)
- Summarise the open storm and flood claims and their latest notes.
  (`gold_claims_overview`)
- Which open claims have fraud flags with a score above 70?
  (`gold_claims_overview`)
- How much home cover do we have in flood and bushfire zones, by state?
  (`gold_catastrophe_exposure`)

**HR and marketing**

- What is attrition by business unit over the last 12 months?
  (`gold_headcount`)
- Is there a gender pay gap within the same pay grade?
  (`gold_pay_equity`)
- Which campaign has the lowest cost per application, and which channel
  converts best? (`gold_campaign_performance`, `gold_channel_performance`)
