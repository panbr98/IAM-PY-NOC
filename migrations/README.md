# Migrations

This repository now reserves `migrations/` for Alembic-based schema history.

The current code still uses `Base.metadata.create_all()` for bootstrap convenience in demo mode.
Before production rollout, the intended path is:

1. generate an initial Alembic revision from the current SQLAlchemy models
2. switch production startup from implicit `create_all()` to migration application
3. keep SQLite demo bootstrap and PostgreSQL production migration flows aligned

The repository includes `alembic.ini` and dependency declarations so the migration path is explicit.
