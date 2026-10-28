-- Alice: executives get the gold (business insight) tables only.

USE CATALOG harbourstone;

-- 1. Gold works. Expect all three regions: APAC, EMEA and AMER.
SELECT region, COUNT(*) AS claims, SUM(incurred_amount) AS incurred
FROM insurance.gold_claims_overview
GROUP BY region;

-- 2. PII in gold stays masked. Expect hashed names and REDACTED email.
SELECT customer_id, first_name, last_name, email, region
FROM retail_banking.gold_customer_360
LIMIT 10;

-- 3. Silver does not. Expect an error, either PERMISSION_DENIED or
-- TABLE_OR_VIEW_NOT_FOUND.
SELECT *
FROM insurance.silver_claims
LIMIT 10;
