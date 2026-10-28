# DEMO-103: Unmasked names and dates of birth for Cassandra Lee

| Field     | Value                                   |
|-----------|-----------------------------------------|
| Type      | Access exception                        |
| Requester | Cassandra Lee (Analytics)               |
| Approver  | Brian Walsh (manager)                   |
| Status    | Approved                                |

## Request

Cassandra needs to reconcile duplicate customer records, which needs the real
names and dates of birth.

## Acceptance criteria

- Cassandra can see unmasked names and dates of birth.
- No other user gains unmasked names or dates of birth.
- Contact details, government IDs and financial account numbers stay
  redacted for Cassandra.
- Cassandra's region restriction (APAC) is unchanged.

## Out of scope

- Any other PII.
- Broad or privileged roles.
