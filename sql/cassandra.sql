USE CATALOG stu_catalog;

--SHOW WHO I AM
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

-- SHOW GOLD DATA
SELECT txn_date, branch_name, region, total_deposits_aud
FROM retail_banking.gold_daily_deposits
ORDER BY txn_date DESC
LIMIT 10;

SELECT region, COUNT(*) AS customers
FROM retail_banking.gold_customer_360
GROUP BY region;

-- FAIL TO ACCESS RAW DATA

SELECT *
FROM retail_banking.bronze_customers
LIMIT 10;

-- CANNOT SEE PII DATA

SELECT customer_id, first_name, last_name, date_of_birth, email, mobile_phone, tax_file_number, region
FROM retail_banking.silver_customers
LIMIT 10;


