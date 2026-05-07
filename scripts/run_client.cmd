@echo off
setlocal
cd /d %~dp0\..
if not defined UV_LINK_MODE set UV_LINK_MODE=copy

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.12+ is required.
  exit /b 1
)

where uv >nul 2>nul
if errorlevel 1 (
  powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

uv sync
uv run python -m client_app.desktop_user_ui.main
