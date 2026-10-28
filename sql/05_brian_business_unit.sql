-- Brian: his BusinessUnit attribute decides which business's data he sees.
-- Run before and after changing BusinessUnit from Insurance to Retail Banking.
--
-- BusinessUnit = Insurance:      query 1 works, query 2 fails.
-- BusinessUnit = Retail Banking: query 1 fails, query 2 works.
-- The policies do not change.

USE CATALOG harbourstone;

-- 1. Insurance
SELECT product_code, region, loss_ratio_pct
FROM insurance.gold_loss_ratio
ORDER BY loss_ratio_pct DESC;

-- 2. Retail Banking
SELECT txn_date, branch_name, region, total_deposits_aud
FROM retail_banking.gold_daily_deposits
ORDER BY txn_date DESC
LIMIT 10;
