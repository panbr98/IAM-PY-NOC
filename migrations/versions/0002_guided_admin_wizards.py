from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_guided_admin_wizards"
down_revision = "0001_noctrix_platform_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connector_queries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False, unique=True),
        sa.Column("system_id", sa.Integer(), sa.ForeignKey("systems.id"), nullable=False),
        sa.Column("connector_id", sa.Integer(), sa.ForeignKey("connectors.id"), nullable=False),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("query_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.add_column("task_mappings", sa.Column("provisioning_mode", sa.String(length=50), nullable=False, server_default="manual"))
    op.add_column("task_mappings", sa.Column("connector_id", sa.Integer(), nullable=True))
    op.add_column("task_mappings", sa.Column("connector_operation", sa.String(length=100), nullable=True))
    op.add_column("task_mappings", sa.Column("connector_query_id", sa.Integer(), nullable=True))
    op.add_column("task_mappings", sa.Column("payload_template_json", sa.Text(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("task_mappings", "payload_template_json")
    op.drop_column("task_mappings", "connector_query_id")
    op.drop_column("task_mappings", "connector_operation")
    op.drop_column("task_mappings", "connector_id")
    op.drop_column("task_mappings", "provisioning_mode")
    op.drop_table("connector_queries")
