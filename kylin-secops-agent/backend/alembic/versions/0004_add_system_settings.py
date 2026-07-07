"""Add system_settings table."""
from datetime import datetime, timezone
from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision = "0004_add_system_settings"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("mfa_enforced_roles", sa.Text(), server_default="[]", nullable=False),
        sa.Column("password_min_length", sa.Integer(), server_default="12", nullable=False),
        sa.Column("password_expire_days", sa.Integer(), server_default="90", nullable=False),
        sa.Column("session_timeout_minutes", sa.Integer(), server_default="60", nullable=False),
        sa.Column("alert_auto_resolve_hours", sa.Integer(), server_default="72", nullable=False),
        sa.Column("heartbeat_timeout_seconds", sa.Integer(), server_default="30", nullable=False),
        sa.Column("max_login_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("lockout_duration_minutes", sa.Integer(), server_default="15", nullable=False),
        sa.Column("ai_auto_analysis", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("notification_enabled", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # Insert default row
    op.execute("INSERT INTO system_settings (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("system_settings")
