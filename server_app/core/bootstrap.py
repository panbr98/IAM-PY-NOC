from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
import hashlib

from server_app.core.audit import record_audit
from server_app.core.database import Base, get_engine, session_scope
from server_app.core.models import (
    ConfigEntry,
    Delegation,
    Identity,
    Resource,
    System,
    TaskMapping,
)
from shared.auth.security import hash_password
from shared.config.settings import get_settings


def initialize_database() -> None:
    Base.metadata.create_all(bind=get_engine())
    with session_scope() as session:
        settings = get_settings()
        _ensure_platform_config(session, settings.database_url)
        if session.query(Identity).count():
            return

        admin = Identity(
            username="admin",
            full_name="Noctrix Admin",
            email="admin@noctrix.local",
            role="super_admin",
            password_hash=hash_password("admin123"),
            status="active",
        )
        manager = Identity(
            username="manager",
            full_name="Manager Demo",
            email="manager@noctrix.local",
            role="manager",
            password_hash=hash_password("manager123"),
            status="active",
        )
        operator = Identity(
            username="operator",
            full_name="Operator Demo",
            email="operator@noctrix.local",
            role="operator",
            password_hash=hash_password("operator123"),
            status="active",
        )
        employee = Identity(
            username="employee",
            full_name="Employee Demo",
            email="employee@noctrix.local",
            role="employee",
            password_hash=hash_password("employee123"),
            status="active",
        )
        session.add_all([admin, manager, operator, employee])
        session.flush()

        employee.manager_id = manager.id

        session.add_all(
            [
                ConfigEntry(key="super_admin.username", value=admin.username),
            ]
        )

        system = System(
            name="Payroll SaaS",
            description="Sample requestable system",
            owner_identity_id=admin.id,
        )
        session.add(system)
        session.flush()

        resource = Resource(
            name="Payroll Analyst",
            system_id=system.id,
            requestable=True,
            description="Sample requestable role",
        )
        session.add(resource)
        session.flush()

        task_mapping = TaskMapping(
            system_id=system.id,
            resource_id=resource.id,
            action="grant",
            task_type="manual_provision",
            default_owner_role="operator",
            sla_hours=8,
        )
        session.add(task_mapping)

        delegation = Delegation(
            delegator_identity_id=manager.id,
            delegate_identity_id=admin.id,
            scope="approval",
            starts_at=datetime.now(UTC),
            ends_at=datetime.now(UTC) + timedelta(days=7),
            status="active",
        )
        session.add(delegation)

        record_audit(
            session,
            actor_identity_id=admin.id,
            event_type="bootstrap.completed",
            entity_type="platform",
            entity_id=None,
            details="Initialized demo dataset and baseline task mapping.",
        )


def _ensure_platform_config(session, database_url: str) -> None:
    defaults = {
        "setup.configured": "false",
        "company.name": "Example Company",
        "environment": "demo",
        "database.url": database_url,
        "tls.enabled": "false",
        "server.fingerprint": _generate_fingerprint(),
    }
    for key, value in defaults.items():
        if not session.get(ConfigEntry, key):
            session.add(ConfigEntry(key=key, value=value))


def _generate_fingerprint() -> str:
    return hashlib.sha256(secrets.token_bytes(32)).hexdigest()[:32].upper()
