from pathlib import Path


def test_server_launcher_contains_uv_and_server_ui() -> None:
    content = Path("scripts/run_server.command").read_text(encoding="utf-8")
    assert "uv sync" in content
    assert "server_app.desktop_admin_ui.main" in content


def test_client_launcher_contains_uv_and_client_ui() -> None:
    content = Path("scripts/run_client.command").read_text(encoding="utf-8")
    assert "uv sync" in content
    assert "client_app.desktop_user_ui.main" in content
