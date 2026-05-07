from __future__ import annotations

from alembic import op

from server_app.core.database import Base
from server_app.core import models  # noqa: F401

revision = "0001_noctrix_platform_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
