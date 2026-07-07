"""fix_audit_login_pk_to_uuid

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-23 21:00:00.000000

Fix: login_logs.id and audit_logs.id were defined as BigInteger(autoincrement=True)
in the Alembic migration, but the ORM models define them as uuid.UUID with
default=uuid.uuid4. This mismatch causes SQLAlchemy to generate UUID primary keys
that cannot be stored in a BigInteger column.

Solution: Drop and recreate both tables with UUID primary keys, matching the
ORM model definitions. This is safe in dev environments where the database
can be reset.
"""
revision = "0005"
down_revision = "0004_add_system_settings"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    """Drop and recreate login_logs and audit_logs with UUID primary keys."""

    # ── Drop existing indexes (order matters for some dialects) ──
    op.drop_index("idx_login_logs_login_at", table_name="login_logs")
    op.drop_index("idx_audit_logs_created_at", table_name="audit_logs")

    # ── Drop tables ──
    op.drop_table("login_logs")
    op.drop_table("audit_logs")

    # ── Recreate login_logs with UUID primary key ──
    op.create_table("login_logs",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(), nullable=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("failure_reason", sa.String(64), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("auth_method", sa.String(32), server_default=sa.text("'password'"), nullable=False),
        sa.Column("login_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ),
    )
    op.create_index("idx_login_logs_login_at", "login_logs", [sa.text("login_at DESC")])

    # ── Recreate audit_logs with UUID primary key ──
    op.create_table("audit_logs",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(), nullable=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("resource_name", sa.String(256), nullable=True),
        sa.Column("detail", postgresql.JSONB(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("result", sa.String(16), server_default=sa.text("'success'"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ),
    )
    op.create_index("idx_audit_logs_created_at", "audit_logs", [sa.text("created_at DESC")])


def downgrade() -> None:
    """Revert to BigInteger autoincrement primary keys."""

    # ── Drop new indexes ──
    op.drop_index("idx_login_logs_login_at", table_name="login_logs")
    op.drop_index("idx_audit_logs_created_at", table_name="audit_logs")

    # ── Drop and recreate with BigInteger ──
    op.drop_table("login_logs")
    op.drop_table("audit_logs")

    op.create_table("login_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(), nullable=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("failure_reason", sa.String(64), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("auth_method", sa.String(32), server_default=sa.text("'password'"), nullable=False),
        sa.Column("login_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ),
    )
    op.create_index("idx_login_logs_login_at", "login_logs", [sa.text("login_at DESC")])

    op.create_table("audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(), nullable=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("resource_name", sa.String(256), nullable=True),
        sa.Column("detail", postgresql.JSONB(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("result", sa.String(16), server_default=sa.text("'success'"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ),
    )
    op.create_index("idx_audit_logs_created_at", "audit_logs", [sa.text("created_at DESC")])
