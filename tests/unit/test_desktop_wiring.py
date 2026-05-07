from __future__ import annotations

import ast
import importlib
import os
import re
from pathlib import Path
from typing import Any

import httpx
import pytest

from client_app.desktop_user_ui.api_client import NoctrixApiClient


def test_api_client_new_endpoint_coverage(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def response(method: str, url: str) -> httpx.Response:
        calls.append((method, url))
        request = httpx.Request(method, url)
        if url.endswith("/scim/v2/Users") or url.endswith("/scim/v2/Groups"):
            return httpx.Response(200, json={"Resources": [], "totalResults": 0, "itemsPerPage": 0}, request=request)
        if method == "POST" and url.endswith("/jobs/run-next"):
            return httpx.Response(200, content=b"null", request=request)
        return httpx.Response(200, json=[], request=request)

    monkeypatch.setattr(httpx, "get", lambda url, **_: response("GET", url))
    monkeypatch.setattr(httpx, "post", lambda url, **_: response("POST", url))
    monkeypatch.setattr(httpx, "put", lambda url, **_: response("PUT", url))
    monkeypatch.setattr(httpx, "delete", lambda url, **_: response("DELETE", url))

    client = NoctrixApiClient("http://server/api/v1")
    client.get_reconciliation_runs()
    client.get_certification_campaigns()
    client.close_certification_campaign(7)
    client.get_pam_checkouts()
    client.checkin_pam_checkout(8)
    client.test_connector(9)
    client.get_connector_runs()
    client.list_connector_queries()
    client.create_connector_query({"name": "Query", "system_id": 1, "connector_id": 9, "operation": "discover", "query": {}, "active": True})
    client.update_connector_query(2, {"name": "Query", "system_id": 1, "connector_id": 9, "operation": "sync", "query": {}, "active": True})
    client.run_connector_query(2)
    client.delete_connector_query(2)
    client.create_job(job_type="reconciliation")
    client.run_next_job()
    client.list_scim_users()
    client.list_scim_groups()
    client.create_scim_group(display_name="Team")
    client.list_scim_mappings()
    client.create_scim_mapping(scim_group_id="group-1", resource_id=2)
    client.update_scim_mapping(4, scim_group_id="group-1", resource_id=2, active=False)
    client.delete_scim_mapping(4)
    client.get_expiring_assignments(14)
    client.revoke_assignment(5, "admin revoke")
    client.list_governance("business-roles")
    client.create_governance("risk-rules", {"name": "Risk"})
    client.update_governance("risk-rules", 3, {"name": "Risk"})
    client.delete_governance("risk-rules", 3)
    client.get_path("/dashboard/summary")
    client.post_path("/jobs", {"job_type": "reconciliation"})
    client.put_path("/settings", {"company_name": "Noctrix", "environment": "demo", "database_url": "sqlite:///x.db", "tls_enabled": False})
    client.delete_path("/systems/3")

    assert calls == [
        ("GET", "http://server/api/v1/reconciliation/runs"),
        ("GET", "http://server/api/v1/certifications/campaigns"),
        ("POST", "http://server/api/v1/certifications/campaigns/7/close"),
        ("GET", "http://server/api/v1/pam/checkouts"),
        ("POST", "http://server/api/v1/pam/checkouts/8/checkin"),
        ("POST", "http://server/api/v1/connectors/9/test"),
        ("GET", "http://server/api/v1/connector-runs"),
        ("GET", "http://server/api/v1/connector-queries"),
        ("POST", "http://server/api/v1/connector-queries"),
        ("PUT", "http://server/api/v1/connector-queries/2"),
        ("POST", "http://server/api/v1/connector-queries/2/run"),
        ("DELETE", "http://server/api/v1/connector-queries/2"),
        ("POST", "http://server/api/v1/jobs"),
        ("POST", "http://server/api/v1/jobs/run-next"),
        ("GET", "http://server/api/v1/scim/v2/Users"),
        ("GET", "http://server/api/v1/scim/v2/Groups"),
        ("POST", "http://server/api/v1/scim/v2/Groups"),
        ("GET", "http://server/api/v1/scim/mappings"),
        ("POST", "http://server/api/v1/scim/mappings"),
        ("PUT", "http://server/api/v1/scim/mappings/4"),
        ("DELETE", "http://server/api/v1/scim/mappings/4"),
        ("GET", "http://server/api/v1/assignments/expiring"),
        ("POST", "http://server/api/v1/assignments/5/revoke"),
        ("GET", "http://server/api/v1/business-roles"),
        ("POST", "http://server/api/v1/risk-rules"),
        ("PUT", "http://server/api/v1/risk-rules/3"),
        ("DELETE", "http://server/api/v1/risk-rules/3"),
        ("GET", "http://server/api/v1/dashboard/summary"),
        ("POST", "http://server/api/v1/jobs"),
        ("PUT", "http://server/api/v1/settings"),
        ("DELETE", "http://server/api/v1/systems/3"),
    ]


def test_desktop_entrypoints_instantiate_offscreen(monkeypatch: pytest.MonkeyPatch) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    app = qt_widgets.QApplication.instance() or qt_widgets.QApplication([])

    client_module = importlib.import_module("client_app.desktop_user_ui.main")
    server_module = importlib.import_module("server_app.desktop_admin_ui.main")
    monkeypatch.setattr(server_module.AdminWindow, "refresh_status", lambda self: None)

    client_window = client_module.ClientWindow()
    server_window = server_module.AdminWindow()

    assert client_window.windowTitle() == "Noctrix Self-Service Portal"
    assert server_window.windowTitle() == "Noctrix Server Setup"
    client_window.close()
    server_window.close()
    app.processEvents()


def test_connected_qt_handlers_exist() -> None:
    for path in [
        Path("client_app/desktop_user_ui/main.py"),
        Path("server_app/desktop_admin_ui/main.py"),
    ]:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        class_methods = _class_methods(tree)
        for handler in re.findall(r"\.connect\(self\.([A-Za-z_][A-Za-z0-9_]*)\)", source):
            assert handler in class_methods, f"{path}: missing handler {handler}"


def test_ui_api_client_methods_exist() -> None:
    api_methods = {
        name
        for name, value in vars(NoctrixApiClient).items()
        if callable(value) and not name.startswith("_")
    }
    for path in [
        Path("client_app/desktop_user_ui/main.py"),
        Path("server_app/desktop_admin_ui/main.py"),
    ]:
        source = path.read_text(encoding="utf-8")
        for method in re.findall(r"self\.api_client\.([A-Za-z_][A-Za-z0-9_]*)\(", source):
            assert method in api_methods, f"{path}: NoctrixApiClient.{method} is not defined"


def test_client_admin_refresh_uses_real_phase_endpoints() -> None:
    source = Path("client_app/desktop_user_ui/main.py").read_text(encoding="utf-8")
    assert "_refresh_pam(pam_secrets, [])" not in source
    assert "_refresh_scim_jobs([], jobs)" not in source
    assert '"/pam/checkouts"' in source
    assert '"/scim/v2/Users"' in source
    assert '"/scim/v2/Groups"' in source


def test_client_admin_has_guided_catalog_assignments_and_scim_controls() -> None:
    source = Path("client_app/desktop_user_ui/main.py").read_text(encoding="utf-8")
    assert "Systems & Resources" in source
    assert "system_name" in source
    assert "Revoke Selected Assignment" in source
    assert "Show Expiring Assignments" in source
    assert "Create Group Mapping" in source
    assert "SCIM & Connectors" in source
    assert "Create Connector" in source
    assert "System Wizard" in source
    assert "Resource Wizard" in source
    assert "Connector Query Wizard" in source
    assert "SCIM Mapping Wizard" in source
    assert "Provisioning Mapping Wizard" in source
    assert "provisioning_mode" in Path("shared/schemas/domain.py").read_text(encoding="utf-8")
    assert "Grant Assignment" not in source


def test_server_app_is_minimal_runtime_setup() -> None:
    source = Path("server_app/desktop_admin_ui/main.py").read_text(encoding="utf-8")
    assert "Runtime and first-run setup only" in source
    assert "stop_service" in source
    assert "kill_service" in source
    assert "Catalog & Governance" not in source


def _class_methods(tree: ast.AST) -> set[str]:
    methods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods.update(item.name for item in node.body if isinstance(item, ast.FunctionDef))
    return methods
