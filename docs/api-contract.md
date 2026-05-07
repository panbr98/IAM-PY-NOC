# API Contract

Base path: `/api/v1`

## Authentication

- `POST /auth/login`
- `GET /me`
- `GET /permissions`

## Platform

- `GET /server-info`

## Core CRUD

- `GET|POST /identities`
- `GET|POST /systems`
- `GET|POST /resources`
- `GET|POST /task-mappings`
- `GET|POST /delegations`

## Workflow

- `GET|POST /access-requests`
- `POST /access-requests/{request_id}/approve`
- `GET /approvals`
- `GET /provisioning/tasks`
- `POST /provisioning/tasks/{task_id}/complete`

## Governance/Audit

- `GET /resource-assignments`
- `GET /audit`
- `POST /identities/{identity_id}/emergency-terminate`

## Phase 2 Governance

- `GET|POST /business-roles`
- `GET|POST /technical-roles`
- `GET|POST /birthright-rules`
- `GET|POST /attribute-access-rules`
- `GET|POST /access-policies`
- `GET|POST /sod-policies`
- `GET|POST /risk-rules`
- `GET|POST /approval-policies`
- `GET /approval-instances`
- `GET /approval-stages`
- `GET|POST /access-expiry-policies`
- `GET /policy-evaluations`
- `GET /assignments/expiring`
- `POST /assignments/{assignment_id}/revoke`

## Reconciliation And Certifications

- `GET|POST /reconciliation/runs`
- `GET /reconciliation/findings`
- `POST /reconciliation/findings/{finding_id}/remediate`
- `GET|POST /certifications/campaigns`
- `POST /certifications/campaigns/{campaign_id}/close`
- `GET /certifications/items`
- `POST /certifications/items/{item_id}/decision`

## PAM-Lite

- `GET|POST /pam/secrets`
- `POST /pam/secrets/{secret_id}/checkout`
- `POST /pam/secrets/{secret_id}/break-glass`
- `GET /pam/checkouts`
- `POST /pam/checkouts/{checkout_id}/checkin`
- `POST /pam/jit`

## Connectors, Jobs, And SCIM

- `GET|POST /connectors`
- `POST /connectors/{connector_id}/test`
- `POST /connectors/{connector_id}/run/{operation}`
- `GET /connector-runs`
- `GET|POST /jobs`
- `POST /jobs/run-next`
- `GET|POST /scim/v2/Users`
- `GET|POST /scim/v2/Groups`
