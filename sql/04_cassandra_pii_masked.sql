-- Cassandra: PII is masked by default.
-- Expect: first_name and last_name are hashes (the same person always gets
-- the same hash, so duplicates still match), date_of_birth is masked, and
-- email, mobile_phone and tax_file_number show REDACTED.
--
-- After Brian approves her request (uncomment "PII Access" in locals.tf and
-- apply), re-run: names and dates of birth are readable; email, phone and
-- TFN stay REDACTED.

USE CATALOG harbourstone;

SELECT customer_id, first_name, last_name, date_of_birth, email, mobile_phone, tax_file_number, region
FROM retail_banking.silver_customers
LIMIT 10;
