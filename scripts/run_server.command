#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[Noctrix] Starting server console"
echo "[Noctrix] Working directory: $(pwd)"
export UV_LINK_MODE="${UV_LINK_MODE:-copy}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.12+ is required."
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "[Noctrix] Syncing dependencies with uv"
uv sync
echo "[Noctrix] Launching PySide6 server admin UI"
uv run python -m server_app.desktop_admin_ui.main
