# Noctrix Architecture

## Product Shape

Noctrix is a single-company, desktop-first IAM/IGA/PAM-lite platform composed of:

- a local or networked FastAPI service
- a PySide6 server administration console that manages the service
- a PySide6 client portal that connects to the service by URL or IP
- a shared schema/auth/config layer used by both desktop applications

## Deployment Profiles

- Demo mode: SQLite on the server machine
- Production mode: PostgreSQL via the same API and domain model

## Bounded Areas

- `auth`
- `server-info`
- `me`
- `permissions`
- `identities`
- `systems`
- `resources`
- `resource-assignments`
- `access-requests`
- `approvals`
- `provisioning`
- `task-mappings`
- `delegations`
- `audit`
- `emergency-termination`

## Server Responsibilities

- authoritative state transitions
- RBAC and permission evaluation
- audit event creation
- manual provisioning task generation from task mappings
- emergency termination fan-out

## Client Responsibilities

- connect to server profiles
- authenticate
- fetch `me` and `permissions`
- render role-appropriate navigation

## Admin Console Responsibilities

- setup wizard entry
- service start and status display
- server metadata display including bind, mode, and fingerprint
- navigation to administrative modules
