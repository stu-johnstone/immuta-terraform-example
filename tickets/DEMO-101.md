# DEMO-101: Baseline analytics access for Cassandra Lee

| Field     | Value                                   |
|-----------|-----------------------------------------|
| Type      | Access request                          |
| Requester | Cassandra Lee (new analytics employee)  |
| Approver  | Brian Walsh (manager)                   |
| Status    | Approved                                |

## Request

Cassandra has joined the Analytics team in APAC and needs access to the
curated Harbourstone data to start work.

## Acceptance criteria

- Members of the Analytics group are subscribed to the curated (silver and
  gold) tables automatically.
- Cassandra is a member of the Analytics group.
- Cassandra only sees rows for her region (APAC), not EMEA or AMER.
- PII is masked for her by default.

## Out of scope

- Unmasked PII (see DEMO-103).
- Raw (bronze) tables.
