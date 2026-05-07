from __future__ import annotations

from sqlalchemy.orm import Session

from server_app.core.models import AuditEvent


def record_audit(
    session: Session,
    *,
    actor_identity_id: int | None,
    event_type: str,
    entity_type: str,
    entity_id: int | None,
    severity: str = "info",
    details: str = "",
) -> AuditEvent:
    event = AuditEvent(
        actor_identity_id=actor_identity_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        severity=severity,
        details=details,
    )
    session.add(event)
    session.flush()
    return event
