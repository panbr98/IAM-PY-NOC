# Test Strategy

## Unit

- RBAC permission resolution
- request and provisioning transitions
- delegation activation
- emergency termination fan-out
- password hashing and secret redaction

## Integration

- bootstrap seeded setup
- login and token issuance
- request -> approval -> provisioning -> assignment flow
- emergency termination audit and task generation

## Script Acceptance

- launchers verify Python
- `uv` presence is ensured
- repeated runs stay idempotent
