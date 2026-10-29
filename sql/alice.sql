USE CATALOG stu_catalog;

WITH personas (application_id, display_name) AS (
  VALUES
    ('0c3870ce-30b2-4e38-b1aa-599f9b6d98d6', 'Cassandra Lee (Analytics, APAC)'),
    ('06567237-b83f-4efc-a3bf-a2a8fc98d2fc', 'Brian Walsh (Manager, APAC)'),
    ('bfdf98f1-a851-45f7-bf0d-9a5b549460cb', 'Alice Morgan (CEO)')
)
SELECT
  current_user() AS principal,
  COALESCE(p.display_name, current_user()) AS display_name
FROM (SELECT 1) AS me
LEFT JOIN personas p ON p.application_id = current_user();

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

