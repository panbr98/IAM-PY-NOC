from server_app.core.rbac import permissions_for_role, require_permission


def test_super_admin_permissions_include_emergency_termination() -> None:
    permissions = permissions_for_role("super_admin")
    assert "emergency_termination.execute" in permissions
    assert require_permission("super_admin", "audit.read")


def test_employee_permissions_are_limited() -> None:
    permissions = permissions_for_role("employee")
    assert "requests.write" in permissions
    assert "audit.read" not in permissions
