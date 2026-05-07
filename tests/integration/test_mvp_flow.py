from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from server_app.core.database import reset_runtime_state
from server_app.core.bootstrap import initialize_database


def auth_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_request_to_assignment_flow(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "mvp.db"
    monkeypatch.setenv("NOCTRIX_DATABASE_URL", f"sqlite:///{db_path}")
    reset_runtime_state()
    initialize_database()
    from server_app.service.app import app

    client = TestClient(app)

    employee_headers = auth_headers(client, "employee", "employee123")
    manager_headers = auth_headers(client, "manager", "manager123")
    operator_headers = auth_headers(client, "operator", "operator123")

    create_response = client.post(
        "/api/v1/access-requests",
        headers=employee_headers,
        json={
            "beneficiary_identity_id": 4,
            "resource_id": 1,
            "reason": "Need payroll reporting access",
            "urgency": "high",
            "comments": "Quarter close",
        },
    )
    assert create_response.status_code == 200
    request_id = create_response.json()["id"]
    assert create_response.json()["status"] == "submitted"

    approval_response = client.post(
        f"/api/v1/access-requests/{request_id}/approve",
        headers=manager_headers,
        json={"decision": "approve", "comment": "Approved"},
    )
    assert approval_response.status_code == 200

    tasks_response = client.get("/api/v1/provisioning/tasks", headers=operator_headers)
    assert tasks_response.status_code == 200
    task_id = tasks_response.json()[0]["id"]

    complete_response = client.post(
        f"/api/v1/provisioning/tasks/{task_id}/complete",
        headers=operator_headers,
        json={"completion_notes": "Provisioned in target system"},
    )
    assert complete_response.status_code == 200

    assignments_response = client.get("/api/v1/resource-assignments", headers=employee_headers)
    assert assignments_response.status_code == 200
    assert assignments_response.json()[0]["status"] == "active"


def test_setup_bootstrap_and_csv_import(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "setup.db"
    monkeypatch.setenv("NOCTRIX_DATABASE_URL", f"sqlite:///{db_path}")
    reset_runtime_state()
    initialize_database()
    from server_app.service.app import app

    client = TestClient(app)

    status_response = client.get("/api/v1/setup-wizard/status")
    assert status_response.status_code == 200
    assert status_response.json()["configured"] is False

    bootstrap_response = client.post(
        "/api/v1/setup-wizard/bootstrap",
        json={
            "company_name": "Noctrix Demo Co",
            "environment": "demo",
            "super_admin_username": "rootadmin",
            "super_admin_full_name": "Root Admin",
            "super_admin_email": "root@example.local",
            "super_admin_password": "VerySecure123",
            "import_sample_data": True,
        },
    )
    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json()["configured"] is True
    assert bootstrap_response.json()["company_name"] == "Noctrix Demo Co"

    admin_headers = auth_headers(client, "rootadmin", "VerySecure123")
    import_response = client.post(
        "/api/v1/identities/import-csv",
        headers=admin_headers,
        json={
            "csv_data": (
                "username,full_name,email,role,manager_username\n"
                "newhire1,New Hire One,newhire1@example.local,employee,manager\n"
                "newhire2,New Hire Two,newhire2@example.local,employee,manager\n"
            ),
            "default_role": "employee",
        },
    )
    assert import_response.status_code == 200
    assert import_response.json()["created_count"] == 2

    identities_response = client.get("/api/v1/identities", headers=admin_headers)
    usernames = {item["username"] for item in identities_response.json()}
    assert {"newhire1", "newhire2"}.issubset(usernames)


def test_emergency_termination_creates_urgent_follow_up(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "termination.db"
    monkeypatch.setenv("NOCTRIX_DATABASE_URL", f"sqlite:///{db_path}")
    reset_runtime_state()
    initialize_database()
    from server_app.service.app import app

    client = TestClient(app)

    admin_headers = auth_headers(client, "admin", "admin123")
    operator_headers = auth_headers(client, "operator", "operator123")

    request_response = client.post(
        "/api/v1/access-requests",
        headers=admin_headers,
        json={
            "beneficiary_identity_id": 4,
            "resource_id": 1,
            "reason": "Seed assignment",
            "urgency": "normal",
            "comments": "",
        },
    )
    request_id = request_response.json()["id"]
    client.post(
        f"/api/v1/access-requests/{request_id}/approve",
        headers=auth_headers(client, "manager", "manager123"),
        json={"decision": "approve", "comment": "ok"},
    )
    task_id = client.get("/api/v1/provisioning/tasks", headers=operator_headers).json()[0]["id"]
    client.post(
        f"/api/v1/provisioning/tasks/{task_id}/complete",
        headers=operator_headers,
        json={"completion_notes": "Provisioned"},
    )

    termination_response = client.post("/api/v1/identities/4/emergency-terminate", headers=admin_headers)
    assert termination_response.status_code == 200
    assert termination_response.json()["status"] == "terminated"

    tasks_response = client.get("/api/v1/provisioning/tasks", headers=operator_headers)
    assert any(task["task_type"] == "urgent_deprovision" for task in tasks_response.json())


def test_delegation_and_queue_views(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "queues.db"
    monkeypatch.setenv("NOCTRIX_DATABASE_URL", f"sqlite:///{db_path}")
    reset_runtime_state()
    initialize_database()
    from server_app.service.app import app

    client = TestClient(app)

    manager_headers = auth_headers(client, "manager", "manager123")
    employee_headers = auth_headers(client, "employee", "employee123")

    delegation_response = client.post(
        "/api/v1/delegations",
        headers=manager_headers,
        json={
            "delegator_identity_id": 2,
            "delegate_identity_id": 4,
            "scope": "approval",
            "starts_at": "2026-05-05T08:00:00",
            "ends_at": "2026-05-12T08:00:00",
        },
    )
    assert delegation_response.status_code == 200
    assert delegation_response.json()["status"] in {"active", "draft"}

    employee_delegations = client.get("/api/v1/delegations", headers=employee_headers)
    assert employee_delegations.status_code == 200
    assert any(item["delegate_identity_id"] == 4 for item in employee_delegations.json())

    request_response = client.post(
        "/api/v1/access-requests",
        headers=employee_headers,
        json={
            "beneficiary_identity_id": 4,
            "resource_id": 1,
            "reason": "Need access for queue test",
            "urgency": "normal",
            "comments": "",
        },
    )
    assert request_response.status_code == 200
    request_id = request_response.json()["id"]

    manager_approvals = client.get("/api/v1/approvals", headers=manager_headers)
    assert manager_approvals.status_code == 200
    assert any(item["access_request_id"] == request_id for item in manager_approvals.json())


def test_admin_catalog_and_task_mapping_crud(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "catalog.db"
    monkeypatch.setenv("NOCTRIX_DATABASE_URL", f"sqlite:///{db_path}")
    reset_runtime_state()
    initialize_database()
    from server_app.service.app import app

    client = TestClient(app)
    admin_headers = auth_headers(client, "admin", "admin123")

    system_response = client.post(
        "/api/v1/systems",
        headers=admin_headers,
        json={
            "name": "Finance ERP",
            "description": "Financial platform",
            "owner_identity_id": 1,
        },
    )
    assert system_response.status_code == 200
    system_id = system_response.json()["id"]

    resource_response = client.post(
        "/api/v1/resources",
        headers=admin_headers,
        json={
            "name": "Finance Approver",
            "system_id": system_id,
            "requestable": True,
            "description": "Approves finance access",
        },
    )
    assert resource_response.status_code == 200
    resource_id = resource_response.json()["id"]

    mapping_response = client.post(
        "/api/v1/task-mappings",
        headers=admin_headers,
        json={
            "system_id": system_id,
            "resource_id": resource_id,
            "action": "grant",
            "task_type": "manual_provision",
            "default_owner_role": "operator",
            "sla_hours": 16,
        },
    )
    assert mapping_response.status_code == 200
    assert mapping_response.json()["resource_id"] == resource_id

    systems_response = client.get("/api/v1/systems", headers=admin_headers)
    resources_response = client.get("/api/v1/resources", headers=admin_headers)
    mappings_response = client.get("/api/v1/task-mappings", headers=admin_headers)

    assert any(item["id"] == system_id for item in systems_response.json())
    assert any(item["id"] == resource_id for item in resources_response.json())
    assert any(item["resource_id"] == resource_id for item in mappings_response.json())


def test_settings_audit_filters_and_update_delete_crud(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "settings.db"
    monkeypatch.setenv("NOCTRIX_DATABASE_URL", f"sqlite:///{db_path}")
    reset_runtime_state()
    initialize_database()
    from server_app.service.app import app

    client = TestClient(app)
    admin_headers = auth_headers(client, "admin", "admin123")

    settings_response = client.get("/api/v1/settings", headers=admin_headers)
    assert settings_response.status_code == 200
    assert settings_response.json()["database_url"].endswith("settings.db")

    update_settings_response = client.put(
        "/api/v1/settings",
        headers=admin_headers,
        json={
            "company_name": "Phase One Co",
            "environment": "production",
            "database_url": "postgresql+psycopg://noctrix:secret@db/noctrix",
            "tls_enabled": True,
        },
    )
    assert update_settings_response.status_code == 200
    assert update_settings_response.json()["company_name"] == "Phase One Co"
    assert update_settings_response.json()["tls_enabled"] is True

    identity_response = client.post(
        "/api/v1/identities",
        headers=admin_headers,
        json={
            "username": "tempuser",
            "full_name": "Temporary User",
            "email": "temp@example.local",
            "role": "employee",
            "manager_id": 2,
        },
    )
    assert identity_response.status_code == 200
    temp_id = identity_response.json()["id"]

    update_identity_response = client.put(
        f"/api/v1/identities/{temp_id}",
        headers=admin_headers,
        json={
            "full_name": "Temporary User Updated",
            "email": "temp.updated@example.local",
            "role": "employee",
            "manager_id": 2,
            "status": "disabled",
        },
    )
    assert update_identity_response.status_code == 200
    assert update_identity_response.json()["status"] == "disabled"

    delete_identity_response = client.delete(f"/api/v1/identities/{temp_id}", headers=admin_headers)
    assert delete_identity_response.status_code == 200
    assert delete_identity_response.json()["deleted"] is True

    audit_response = client.get(
        "/api/v1/audit",
        headers=admin_headers,
        params={"entity_type": "identity", "search": "tempuser"},
    )
    assert audit_response.status_code == 200
    assert any(event["event_type"] == "identity.updated" for event in audit_response.json())

    critical_audit_response = client.get(
        "/api/v1/audit",
        headers=admin_headers,
        params={"severity": "critical"},
    )
    assert critical_audit_response.status_code == 200
    assert critical_audit_response.json() == []


def test_phase2_birthright_roles_and_recalculation(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "phase2_roles.db"
    monkeypatch.setenv("NOCTRIX_DATABASE_URL", f"sqlite:///{db_path}")
    reset_runtime_state()
    initialize_database()
    from server_app.service.app import app

    client = TestClient(app)
    admin_headers = auth_headers(client, "admin", "admin123")

    technical_role = client.post(
        "/api/v1/technical-roles",
        headers=admin_headers,
        json={
            "name": "TR Payroll",
            "description": "Payroll bundle",
            "requestable": True,
            "active": True,
            "resource_ids": [1],
        },
    )
    assert technical_role.status_code == 200
    technical_role_id = technical_role.json()["id"]

    business_role = client.post(
        "/api/v1/business-roles",
        headers=admin_headers,
        json={
            "name": "BR Finance",
            "description": "Finance access",
            "requestable": True,
            "risk_level": "medium",
            "active": True,
            "technical_role_ids": [technical_role_id],
            "resource_ids": [],
        },
    )
    assert business_role.status_code == 200
    business_role_id = business_role.json()["id"]

    birthright = client.post(
        "/api/v1/birthright-rules",
        headers=admin_headers,
        json={
            "name": "Finance Employees",
            "attribute_name": "email_domain",
            "operator": "equals",
            "expected_value": "noctrix.local",
            "target_type": "business_role",
            "target_id": business_role_id,
            "active": True,
            "grant_basis": "birthright",
        },
    )
    assert birthright.status_code == 200

    recalc = client.post("/api/v1/identities/4/governance/recalculate", headers=admin_headers)
    assert recalc.status_code == 200
    assert recalc.json()["assignments_created"] >= 1

    assignments = client.get("/api/v1/resource-assignments", headers=auth_headers(client, "employee", "employee123"))
    assert assignments.status_code == 200
    assert any(item["source_type"] == "birthright" for item in assignments.json())


def test_phase2_sod_risk_and_staged_approvals(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "phase2_approval.db"
    monkeypatch.setenv("NOCTRIX_DATABASE_URL", f"sqlite:///{db_path}")
    reset_runtime_state()
    initialize_database()
    from server_app.service.app import app

    client = TestClient(app)
    admin_headers = auth_headers(client, "admin", "admin123")
    manager_headers = auth_headers(client, "manager", "manager123")

    system = client.post(
        "/api/v1/systems",
        headers=admin_headers,
        json={"name": "Privileged SaaS", "description": "High risk", "owner_identity_id": 1},
    )
    system_id = system.json()["id"]
    resource = client.post(
        "/api/v1/resources",
        headers=admin_headers,
        json={"name": "Privileged Admin", "system_id": system_id, "requestable": True, "description": "Privileged"},
    )
    resource_id = resource.json()["id"]

    client.post(
        "/api/v1/access-policies",
        headers=admin_headers,
        json={
            "name": "Privileged Policy",
            "resource_id": resource_id,
            "system_id": None,
            "business_role_id": None,
            "technical_role_id": None,
            "max_duration_days": 10,
            "privileged": True,
            "base_risk_score": 20,
            "require_justification": True,
            "active": True,
        },
    )
    client.post(
        "/api/v1/risk-rules",
        headers=admin_headers,
        json={
            "name": "Critical urgency",
            "condition_type": "urgency",
            "condition_value": "critical",
            "score": 25,
            "severity": "high",
            "active": True,
        },
    )
    client.post(
        "/api/v1/approval-policies",
        headers=admin_headers,
        json={
            "name": "High Risk Route",
            "scope_type": "resource",
            "scope_id": resource_id,
            "min_risk_score": 0,
            "sequential": True,
            "active": True,
            "stages": [
                {"stage_order": 1, "mode": "all", "approver_type": "manager", "approver_value": "", "required_count": 1},
                {"stage_order": 2, "mode": "all", "approver_type": "risk_security_role", "approver_value": "super_admin", "required_count": 1},
            ],
        },
    )
    client.post(
        "/api/v1/sod-policies",
        headers=admin_headers,
        json={
            "name": "Privileged conflict",
            "description": "Warn on conflict",
            "mode": "warn",
            "severity": "high",
            "active": True,
            "resource_pairs": [[1, resource_id]],
        },
    )

    base_request = client.post(
        "/api/v1/access-requests",
        headers=auth_headers(client, "employee", "employee123"),
        json={
            "beneficiary_identity_id": 4,
            "resource_id": 1,
            "reason": "Need baseline payroll access",
            "urgency": "normal",
            "comments": "",
        },
    )
    client.post(
        f"/api/v1/access-requests/{base_request.json()['id']}/approve",
        headers=manager_headers,
        json={"decision": "approve", "comment": "baseline"},
    )
    base_task_id = client.get("/api/v1/provisioning/tasks", headers=auth_headers(client, "operator", "operator123")).json()[0]["id"]
    client.post(
        f"/api/v1/provisioning/tasks/{base_task_id}/complete",
        headers=auth_headers(client, "operator", "operator123"),
        json={"completion_notes": "baseline complete"},
    )

    request = client.post(
        "/api/v1/access-requests",
        headers=auth_headers(client, "employee", "employee123"),
        json={
            "beneficiary_identity_id": 4,
            "resource_id": resource_id,
            "reason": "Need privileged support access",
            "urgency": "critical",
            "comments": "urgent",
        },
    )
    assert request.status_code == 200
    assert request.json()["risk_score"] >= 75
    assert request.json()["status"] == "submitted"

    evaluations = client.get("/api/v1/policy-evaluations", headers=admin_headers, params={"access_request_id": request.json()["id"]})
    assert evaluations.status_code == 200
    assert any(item["result_type"] == "sod_policy" for item in evaluations.json())

    approvals = client.get("/api/v1/approvals", headers=manager_headers)
    assert any(item["access_request_id"] == request.json()["id"] for item in approvals.json())

    approve_stage_1 = client.post(
        f"/api/v1/access-requests/{request.json()['id']}/approve",
        headers=manager_headers,
        json={"decision": "approve", "comment": "Manager ok"},
    )
    assert approve_stage_1.status_code == 200

    stage_instances = client.get("/api/v1/approval-instances", headers=admin_headers, params={"access_request_id": request.json()["id"]})
    assert stage_instances.status_code == 200
    assert any(item["approver_identity_id"] == 1 for item in stage_instances.json())

    approve_stage_2 = client.post(
        f"/api/v1/access-requests/{request.json()['id']}/approve",
        headers=admin_headers,
        json={"decision": "approve", "comment": "Risk approved"},
    )
    assert approve_stage_2.status_code == 200

    tasks = client.get("/api/v1/provisioning/tasks", headers=auth_headers(client, "operator", "operator123"))
    assert any(item["resource_id"] == resource_id for item in tasks.json())


def test_phase2_expiry_revoke_and_self_approval_block(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "phase2_expiry.db"
    monkeypatch.setenv("NOCTRIX_DATABASE_URL", f"sqlite:///{db_path}")
    reset_runtime_state()
    initialize_database()
    from server_app.service.app import app

    client = TestClient(app)
    admin_headers = auth_headers(client, "admin", "admin123")
    operator_headers = auth_headers(client, "operator", "operator123")
    employee_headers = auth_headers(client, "employee", "employee123")

    client.post(
        "/api/v1/access-expiry-policies",
        headers=admin_headers,
        json={
            "name": "Payroll expiry",
            "resource_id": 1,
            "business_role_id": None,
            "technical_role_id": None,
            "default_duration_days": 3,
            "active": True,
        },
    )

    request = client.post(
        "/api/v1/access-requests",
        headers=employee_headers,
        json={
            "beneficiary_identity_id": 4,
            "resource_id": 1,
            "reason": "Need payroll access",
            "urgency": "normal",
            "comments": "",
        },
    )
    request_id = request.json()["id"]

    self_approval = client.post(
        f"/api/v1/access-requests/{request_id}/approve",
        headers=employee_headers,
        json={"decision": "approve", "comment": "self"},
    )
    assert self_approval.status_code == 403 or self_approval.status_code == 404

    manager_approval = client.post(
        f"/api/v1/access-requests/{request_id}/approve",
        headers=auth_headers(client, "manager", "manager123"),
        json={"decision": "approve", "comment": "manager"},
    )
    assert manager_approval.status_code == 200

    task_id = client.get("/api/v1/provisioning/tasks", headers=operator_headers).json()[0]["id"]
    task_complete = client.post(
        f"/api/v1/provisioning/tasks/{task_id}/complete",
        headers=operator_headers,
        json={"completion_notes": "provisioned"},
    )
    assert task_complete.status_code == 200

    expiring = client.get("/api/v1/assignments/expiring", headers=operator_headers, params={"within_days": 10})
    assert expiring.status_code == 200
    assert len(expiring.json()) >= 1
    assignment_id = expiring.json()[0]["id"]

    revoke = client.post(f"/api/v1/assignments/{assignment_id}/revoke", headers=operator_headers, params={"notes": "expired soon"})
    assert revoke.status_code == 200
    assert revoke.json()["status"] == "revocation_pending"
