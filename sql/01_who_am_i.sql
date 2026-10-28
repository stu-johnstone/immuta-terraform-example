-- Who am I? Run first, as each persona.
--
-- For a service principal, current_user() returns its application ID (a
-- UUID), not a name. Databricks SQL has no function that returns a service
-- principal's display name, so map the IDs here. Copy each application ID
-- from the workspace admin settings (Identity and access > Service
-- principals).

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
