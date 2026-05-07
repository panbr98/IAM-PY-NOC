from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from server_app.core.bootstrap import initialize_database
from server_app.core.database import reset_runtime_state


def auth_headers(client: TestClient, username: str = "admin", password: str = "admin123") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def app_client(monkeypatch, tmp_path: Path, name: str) -> tuple[TestClient, dict[str, str]]:
    monkeypatch.setenv("NOCTRIX_DATABASE_URL", f"sqlite:///{tmp_path / name}")
    reset_runtime_state()
    initialize_database()
    from server_app.service.app import app

    client = TestClient(app)
    return client, auth_headers(client)


def seed_assignment(client: TestClient) -> None:
    employee = auth_headers(client, "employee", "employee123")
    manager = auth_headers(client, "manager", "manager123")
    operator = auth_headers(client, "operator", "operator123")
    request = client.post(
        "/api/v1/access-requests",
        headers=employee,
        json={"beneficiary_identity_id": 4, "resource_id": 1, "reason": "seed", "urgency": "normal", "comments": ""},
    )
    assert request.status_code == 200
    client.post(f"/api/v1/access-requests/{request.json()['id']}/approve", headers=manager, json={"decision": "approve", "comment": "ok"})
    task = client.get("/api/v1/provisioning/tasks", headers=operator).json()[0]
    client.post(f"/api/v1/provisioning/tasks/{task['id']}/complete", headers=operator, json={"completion_notes": "done"})


def test_system_resource_assignment_relationship(monkeypatch, tmp_path: Path) -> None:
    client, admin = app_client(monkeypatch, tmp_path, "system_resource_assignment.db")
    employee = auth_headers(client, "employee", "employee123")
    manager = auth_headers(client, "manager", "manager123")
    operator = auth_headers(client, "operator", "operator123")

    system = client.post("/api/v1/systems", headers=admin, json={"name": "Finance Suite", "description": "Finance"})
    assert system.status_code == 200
    resource = client.post(
        "/api/v1/resources",
        headers=admin,
        json={"name": "Ledger Approver", "system_id": system.json()["id"], "requestable": True, "description": "Approval role"},
    )
    assert resource.status_code == 200
    mapping = client.post(
        "/api/v1/task-mappings",
        headers=admin,
        json={"system_id": system.json()["id"], "resource_id": resource.json()["id"], "action": "grant", "task_type": "manual_provision", "default_owner_role": "operator", "sla_hours": 24},
    )
    assert mapping.status_code == 200

    request = client.post(
        "/api/v1/access-requests",
        headers=employee,
        json={"beneficiary_identity_id": 4, "resource_id": resource.json()["id"], "reason": "monthly close", "urgency": "normal", "comments": ""},
    )
    assert request.status_code == 200
    approval = client.post(f"/api/v1/access-requests/{request.json()['id']}/approve", headers=manager, json={"decision": "approve", "comment": "ok"})
    assert approval.status_code == 200
    task = client.get("/api/v1/provisioning/tasks", headers=operator).json()[0]
    complete = client.post(f"/api/v1/provisioning/tasks/{task['id']}/complete", headers=operator, json={"completion_notes": "done"})
    assert complete.status_code == 200

    assignments = client.get("/api/v1/resource-assignments", headers=admin)
    assert assignments.status_code == 200
    assignment = next(item for item in assignments.json() if item["resource_id"] == resource.json()["id"])
    resources = {item["id"]: item for item in client.get("/api/v1/resources", headers=admin).json()}
    systems = {item["id"]: item for item in client.get("/api/v1/systems", headers=admin).json()}
    assignment_resource = resources[assignment["resource_id"]]
    assert systems[assignment_resource["system_id"]]["name"] == "Finance Suite"


def test_reconciliation_findings_and_remediation(monkeypatch, tmp_path: Path) -> None:
    client, admin = app_client(monkeypatch, tmp_path, "recon.db")
    run = client.post(
        "/api/v1/reconciliation/runs",
        headers=admin,
        json={
            "name": "Nightly diff",
            "desired_access": [{"identity_id": 4, "resource_id": 1}],
            "actual_access": [
                {"identity_id": 4, "resource_id": 1},
                {"identity_id": 4, "resource_id": 2, "account": "employee", "privileged": True},
            ],
        },
    )
    assert run.status_code == 200
    findings = client.get("/api/v1/reconciliation/findings", headers=admin, params={"run_id": run.json()["id"]})
    assert findings.status_code == 200
    assert findings.json()[0]["finding_type"] == "privileged_finding"
    action = client.post(f"/api/v1/reconciliation/findings/{findings.json()[0]['id']}/remediate", headers=admin)
    assert action.status_code == 200
    assert action.json()["status"] == "queued"


def test_certification_revoke_creates_task(monkeypatch, tmp_path: Path) -> None:
    client, admin = app_client(monkeypatch, tmp_path, "cert.db")
    seed_assignment(client)
    campaign = client.post("/api/v1/certifications/campaigns", headers=admin, json={"name": "Quarterly", "reviewer_identity_id": 1})
    assert campaign.status_code == 200
    items = client.get("/api/v1/certifications/items", headers=admin, params={"campaign_id": campaign.json()["id"]})
    assert items.status_code == 200
    decision = client.post(f"/api/v1/certifications/items/{items.json()[0]['id']}/decision", headers=admin, json={"decision": "revoke", "notes": "No longer needed"})
    assert decision.status_code == 200
    tasks = client.get("/api/v1/provisioning/tasks", headers=auth_headers(client, "operator", "operator123"))
    assert any(task["task_type"] == "certification_revoke" for task in tasks.json())


def test_pam_checkout_break_glass_and_emergency_cleanup(monkeypatch, tmp_path: Path) -> None:
    client, admin = app_client(monkeypatch, tmp_path, "pam.db")
    secret = client.post("/api/v1/pam/secrets", headers=admin, json={"name": "Payroll root", "account_username": "root", "secret_value": "S3cret!"})
    assert secret.status_code == 200
    checkout = client.post(f"/api/v1/pam/secrets/{secret.json()['id']}/checkout", headers=admin, json={"reason": "maintenance", "duration_minutes": 30})
    assert checkout.status_code == 200
    assert checkout.json()["revealed_secret"] == "S3cret!"
    checkin = client.post(f"/api/v1/pam/checkouts/{checkout.json()['id']}/checkin", headers=admin)
    assert checkin.status_code == 200
    employee_checkout = client.post(
        f"/api/v1/pam/secrets/{secret.json()['id']}/checkout",
        headers=auth_headers(client, "employee", "employee123"),
        json={"reason": "user support", "duration_minutes": 30},
    )
    assert employee_checkout.status_code == 200
    break_glass = client.post(f"/api/v1/pam/secrets/{secret.json()['id']}/break-glass", headers=admin, json={"reason": "incident", "duration_minutes": 15})
    assert break_glass.status_code == 200
    assert break_glass.json()["break_glass"] is True
    termination = client.post("/api/v1/identities/4/emergency-terminate", headers=admin)
    assert termination.status_code == 200
    checkouts = client.get("/api/v1/pam/checkouts", headers=admin)
    employee_rows = [item for item in checkouts.json() if item["requester_identity_id"] == 4]
    assert employee_rows and all(item["status"] == "terminated" for item in employee_rows)


def test_connectors_jobs_and_scim(monkeypatch, tmp_path: Path) -> None:
    client, admin = app_client(monkeypatch, tmp_path, "connectors.db")
    system = client.post("/api/v1/systems", headers=admin, json={"name": "SCIM Target", "description": "Mapped app"})
    assert system.status_code == 200
    resource = client.post(
        "/api/v1/resources",
        headers=admin,
        json={"name": "SCIM Group Resource", "system_id": system.json()["id"], "requestable": True, "description": "Mapped by SCIM"},
    )
    assert resource.status_code == 200
    scim_connector = client.post(
        "/api/v1/connectors",
        headers=admin,
        json={"name": "SCIM Inbound", "connector_type": "scim", "system_id": system.json()["id"], "dry_run": True, "config": {}},
    )
    assert scim_connector.status_code == 200
    missing_system = client.post(
        "/api/v1/connectors",
        headers=admin,
        json={"name": "Broken SCIM", "connector_type": "scim", "dry_run": True, "config": {}},
    )
    assert missing_system.status_code == 422
    connector = client.post(
        "/api/v1/connectors",
        headers=admin,
        json={"name": "CSV HR", "connector_type": "csv", "dry_run": True, "config": {"csv_data": "username,email\nu,u@example.local\n"}},
    )
    assert connector.status_code == 200
    run = client.post(f"/api/v1/connectors/{connector.json()['id']}/run/sync", headers=admin)
    assert run.status_code == 200
    assert "CSV parsed" in run.json()["summary"]

    job = client.post("/api/v1/jobs", headers=admin, json={"job_type": "connector_sync", "payload": {"connector_id": connector.json()["id"]}})
    assert job.status_code == 200
    completed = client.post("/api/v1/jobs/run-next", headers=admin)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    user = client.post(
        "/api/v1/scim/v2/Users",
        headers=admin,
        json={"userName": "scim.user", "displayName": "SCIM User", "active": True, "emails": [{"value": "scim@example.local"}]},
    )
    assert user.status_code == 200
    group = client.post("/api/v1/scim/v2/Groups", headers=admin, json={"displayName": "SCIM Group", "members": [{"value": user.json()["id"]}]})
    assert group.status_code == 200
    mapping = client.post(
        "/api/v1/scim/mappings",
        headers=admin,
        json={"scim_group_id": group.json()["id"], "resource_id": resource.json()["id"]},
    )
    assert mapping.status_code == 200
    assert mapping.json()["source_path"] == f"Groups:{group.json()['id']}"
    assert mapping.json()["target_path"] == f"resources:{resource.json()['id']}"
    users = client.get("/api/v1/scim/v2/Users", headers=admin)
    assert users.json()["totalResults"] == 1
    mappings = client.get("/api/v1/scim/mappings", headers=admin)
    assert mappings.status_code == 200
    assert mappings.json()[0]["resource_id"] == resource.json()["id"]


def test_guided_resource_manual_mapping_and_connector_query(monkeypatch, tmp_path: Path) -> None:
    client, admin = app_client(monkeypatch, tmp_path, "guided_manual.db")
    system = client.post("/api/v1/systems", headers=admin, json={"name": "Guided System", "description": "wizard", "owner_identity_id": 1})
    assert system.status_code == 200
    resource = client.post("/api/v1/resources", headers=admin, json={"name": "Guided Resource", "system_id": system.json()["id"], "requestable": True, "description": "wizard"})
    assert resource.status_code == 200
    mapping = client.post(
        "/api/v1/task-mappings",
        headers=admin,
        json={"system_id": system.json()["id"], "resource_id": resource.json()["id"], "action": "grant", "trigger_event": "approval_approved", "task_type": "manual_provision", "default_owner_role": "operator", "sla_hours": 24, "provisioning_mode": "manual"},
    )
    assert mapping.status_code == 200
    assert mapping.json()["provisioning_mode"] == "manual"

    connector = client.post("/api/v1/connectors", headers=admin, json={"name": "Guided CSV", "connector_type": "csv", "system_id": system.json()["id"], "dry_run": True, "config": {}})
    assert connector.status_code == 200
    query = client.post("/api/v1/connector-queries", headers=admin, json={"name": "Guided Discover", "system_id": system.json()["id"], "connector_id": connector.json()["id"], "operation": "discover", "query": {"scope": "groups"}, "active": True})
    assert query.status_code == 200
    run = client.post(f"/api/v1/connector-queries/{query.json()['id']}/run", headers=admin)
    assert run.status_code == 200
    assert run.json()["operation"] == "discover"


def test_automatic_mapping_success_and_failure(monkeypatch, tmp_path: Path) -> None:
    client, admin = app_client(monkeypatch, tmp_path, "automatic_mapping.db")
    manager = auth_headers(client, "manager", "manager123")
    employee = auth_headers(client, "employee", "employee123")
    operator = auth_headers(client, "operator", "operator123")

    system = client.post("/api/v1/systems", headers=admin, json={"name": "Automatic System", "description": ""}).json()
    ok_resource = client.post("/api/v1/resources", headers=admin, json={"name": "Auto OK", "system_id": system["id"], "requestable": True, "description": ""}).json()
    fail_resource = client.post("/api/v1/resources", headers=admin, json={"name": "Auto Fail", "system_id": system["id"], "requestable": True, "description": ""}).json()
    ok_connector = client.post("/api/v1/connectors", headers=admin, json={"name": "Auto OK Connector", "connector_type": "scim", "system_id": system["id"], "dry_run": True, "config": {}}).json()
    fail_connector = client.post("/api/v1/connectors", headers=admin, json={"name": "Auto Fail Connector", "connector_type": "scim", "system_id": system["id"], "dry_run": True, "config": {"fail_operations": ["provision"]}}).json()

    for resource, connector in [(ok_resource, ok_connector), (fail_resource, fail_connector)]:
        mapping = client.post(
            "/api/v1/task-mappings",
            headers=admin,
            json={"system_id": system["id"], "resource_id": resource["id"], "action": "grant", "trigger_event": "approval_approved", "task_type": "automatic_provision", "default_owner_role": "operator", "sla_hours": 1, "provisioning_mode": "automatic", "connector_id": connector["id"], "connector_operation": "provision", "payload_template": {"source": "wizard"}},
        )
        assert mapping.status_code == 200

    ok_request = client.post("/api/v1/access-requests", headers=employee, json={"beneficiary_identity_id": 4, "resource_id": ok_resource["id"], "reason": "ok", "urgency": "normal", "comments": ""}).json()
    assert client.post(f"/api/v1/access-requests/{ok_request['id']}/approve", headers=manager, json={"decision": "approve", "comment": "ok"}).status_code == 200
    ok_tasks = [task for task in client.get("/api/v1/provisioning/tasks", headers=operator).json() if task["resource_id"] == ok_resource["id"]]
    assert ok_tasks[0]["status"] == "completed"
    assignments = client.get("/api/v1/resource-assignments", headers=admin).json()
    assert any(item["resource_id"] == ok_resource["id"] and item["identity_id"] == 4 for item in assignments)

    fail_request = client.post("/api/v1/access-requests", headers=employee, json={"beneficiary_identity_id": 4, "resource_id": fail_resource["id"], "reason": "fail", "urgency": "normal", "comments": ""}).json()
    assert client.post(f"/api/v1/access-requests/{fail_request['id']}/approve", headers=manager, json={"decision": "approve", "comment": "fail"}).status_code == 200
    failed_tasks = [task for task in client.get("/api/v1/provisioning/tasks", headers=operator).json() if task["resource_id"] == fail_resource["id"]]
    assert failed_tasks[0]["status"] == "failed"
    assignments = client.get("/api/v1/resource-assignments", headers=admin).json()
    assert not any(item["resource_id"] == fail_resource["id"] and item["identity_id"] == 4 for item in assignments)
