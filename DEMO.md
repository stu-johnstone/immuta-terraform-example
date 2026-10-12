# Immuta Govern Demo

## Story

- **Cassandra:** new analytics employee, access by request and policy.
- **Brian:** manager whose access changes when his Entra attributes change.
- **Alice:** CEO who uses AI to get governed business insights.

## Cassandra: baseline access

- Cassandra submits an access request through ServiceNow.
- Her Entra attributes establish her team and region.
- Immuta grants baseline access to her region.
- PII is masked by default.
- She cannot access data outside her region.

> “Cassandra gets productive quickly, but her access is still limited by region and data sensitivity.”

## Brian: changing business area

- Brian starts in Insurance and can see Insurance data.
- His business-unit tag changes to Retail Banking in Entra.
- No Immuta policy changes are needed.
- His access automatically changes to reflect Retail Banking.

> “The policy did not change. Brian’s attributes changed, so the access decision changed.”

## Cassandra: requesting unmasked PII

- Cassandra needs to reconcile duplicate customer records.
- She requests access to unmasked names and dates of birth.
- Brian reviews the business reason and approves the exception.
- Cassandra receives the specific access she needs, not broad privileged access.

## Alice: AI-driven access

- Alice asks: “What is driving the increase in Retail Banking claims?”
- She has executive entitlement to business insights, but no standing raw-data role.
- An AI agent acts on her behalf with temporary, task-specific access.
- PII remains governed and unnecessary sensitive data is not exposed.
- The audit trail shows Alice, the agent, the data accessed, and the policy applied.

> “The agent is not using Alice’s unrestricted credentials. It is acting on her behalf with governed access for this task.”

## Closing message

> “Different people need different access, and their needs change over time. Immuta uses identity, data classification, and policy to deliver the right access without broad standing permissions.”