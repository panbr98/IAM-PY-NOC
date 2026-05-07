# Noctrix

Noctrix is a desktop-first IAM/IGA/PAM-lite platform with:

- a PySide6 server admin console
- a FastAPI backend service
- a PySide6 client portal
- shared auth, config, crypto, and API schemas

This repository currently provides the foundation and MVP vertical-slice scaffold described in `docs/`.

## Layout

- `server_app/` server admin UI, backend service, core domain, connectors, worker hooks
- `client_app/` desktop user portal
- `shared/` config, auth, crypto, and shared schemas
- `scripts/` bootstrap launchers for Windows and macOS
- `tests/` unit and integration coverage
- `docs/` architecture package and backlog

## Quick Start

Use the bootstrap scripts:

- macOS server: `scripts/run_server.command`
- macOS client: `scripts/run_client.command`
- Windows server: `scripts/run_server.cmd`
- Windows client: `scripts/run_client.cmd`

Or run directly with `uv`:

```bash
uv sync
uv run python -m server_app.service.app
uv run python -m client_app.desktop_user_ui.main
```
