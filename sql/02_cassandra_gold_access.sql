-- Cassandra: she can query a gold table, but only sees APAC rows.
-- Expect: rows are returned, and the region breakdown shows APAC only (no
-- EMEA or AMER).

USE CATALOG stu_catalog;

SELECT txn_date, branch_name, region, total_deposits_aud
FROM retail_banking.gold_daily_deposits
ORDER BY txn_date DESC
LIMIT 10;

SELECT region, COUNT(*) AS customers
FROM retail_banking.gold_customer_360
GROUP BY region;
