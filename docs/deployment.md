# Deployment Notes

## Modes

- Demo mode uses SQLite and the bootstrap data path
- Production mode is intended to use PostgreSQL via `psycopg`

## Current Production-Oriented Settings

- persisted platform settings now track:
  - company name
  - environment
  - database URL
  - TLS enabled flag
  - server fingerprint
- server fingerprint is generated and stored in the database config table on bootstrap

## Launchers

The launcher scripts still target a developer/operator workflow:

- ensure Python exists
- ensure `uv` exists
- `uv sync`
- start the desktop app

## Remaining Production Hardening

- replace `create_all()` startup with Alembic migrations
- add TLS certificate generation and rotation
- wire runtime server host/port and TLS settings into managed service startup
- validate PostgreSQL startup end-to-end outside demo mode
