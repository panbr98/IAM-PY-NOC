from __future__ import annotations

from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from server_app.core.database import get_session_factory
from server_app.core.models import Identity
from server_app.core.rbac import require_permission
from shared.auth.security import decode_access_token
from shared.config.settings import get_settings

bearer_scheme = HTTPBearer()


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def get_current_identity(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Identity:
    settings = get_settings()
    try:
        payload = decode_access_token(credentials.credentials, settings)
    except Exception as exc:  # pragma: no cover - auth library raises multiple types
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.") from exc

    identity = db.get(Identity, int(payload["sub"]))
    if not identity or identity.status not in {"active", "disabled"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identity unavailable.")
    return identity


def require(permission: str):
    def dependency(identity: Identity = Depends(get_current_identity)) -> Identity:
        if not require_permission(identity.role, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.")
        return identity

    return dependency
