-- Cassandra: no access to raw data.
-- The Analytics subscription covers the curated (silver and gold) tables only,
-- so bronze is out of reach.
-- Expect: an error, either PERMISSION_DENIED or TABLE_OR_VIEW_NOT_FOUND.

USE CATALOG harbourstone;

SELECT *
FROM retail_banking.bronze_customers
LIMIT 10;
