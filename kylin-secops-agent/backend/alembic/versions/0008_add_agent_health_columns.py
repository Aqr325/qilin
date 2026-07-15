"""add health_score and last_status_change to agents table

Revision ID: 0008_add_agent_health_columns
Revises: 0007_add_agent_tasks
Create Date: 2026-06-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "0008_add_agent_health_columns"
down_revision = "0007_add_agent_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add health_score and last_status_change columns to agents table."""
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        # SQLite doesn't support ALTER TABLE ADD COLUMN with server_default well;
        # we recreate the table with the new columns.
        try:
            op.execute(sa.text("ALTER TABLE agents RENAME TO agents_no_health"))
            op.create_table(
                "agents",
                sa.Column("id", sa.String(36), primary_key=True, nullable=False),
                sa.Column("agent_id", sa.String(128), nullable=False, unique=True, index=True),
                sa.Column("credential", sa.String(128), nullable=False, unique=True, index=True),
                sa.Column("hostname", sa.String(256), nullable=False),
                sa.Column("ip_address", sa.String()),
                sa.Column("os_version", sa.String(64), nullable=False),
                sa.Column("kernel_version", sa.String(64)),
                sa.Column("agent_version", sa.String(32), nullable=False),
                sa.Column("cpu_cores", sa.Integer(), nullable=False),
                sa.Column("total_memory", sa.BigInteger(), nullable=False),
                sa.Column("disk_total", sa.BigInteger()),
                sa.Column("status", sa.String(20), nullable=False, server_default="offline", index=True),
                sa.Column("last_heartbeat", sa.DateTime(timezone=True), index=True),
                sa.Column("last_heartbeat_ip", sa.String()),
                sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
                sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
                sa.Column("tags", sa.JSON(), server_default="[]"),
                sa.Column("metadata", sa.JSON(), server_default="{}"),
                sa.Column("config_version", sa.Integer(), server_default="0"),
                sa.Column("health_score", sa.Integer(), nullable=False, server_default="80"),
                sa.Column("last_status_change", sa.DateTime(timezone=True)),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
                sa.Column("is_deleted", sa.Boolean(), server_default="0", nullable=False),
                sa.Column("deleted_at", sa.DateTime(timezone=True)),
            )
            op.execute(sa.text(
                "INSERT INTO agents (id, agent_id, credential, hostname, ip_address, os_version, "
                "kernel_version, agent_version, cpu_cores, total_memory, disk_total, status, "
                "last_heartbeat, last_heartbeat_ip, registered_at, first_seen_at, tags, metadata, "
                "config_version, health_score, last_status_change, created_at, updated_at, is_deleted, deleted_at) "
                "SELECT id, agent_id, credential, hostname, ip_address, os_version, "
                "kernel_version, agent_version, cpu_cores, total_memory, disk_total, status, "
                "last_heartbeat, last_heartbeat_ip, registered_at, first_seen_at, tags, metadata, "
                "config_version, 80, NULL, created_at, updated_at, is_deleted, deleted_at "
                "FROM agents_no_health"
            ))
            op.drop_table("agents_no_health")
            print("Added health_score and last_status_change columns to agents table (SQLite)")
        except Exception as e:
            print(f"Migration error: {e}")
    else:
        # PostgreSQL - simple ALTER TABLE
        op.add_column(
            "agents",
            sa.Column(
                "health_score",
                sa.Integer(),
                nullable=False,
                server_default="80",
                comment="健康评分(0-100)",
            ),
        )
        op.add_column(
            "agents",
            sa.Column(
                "last_status_change",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="最后状态变化时间",
            ),
        )
        print("Added health_score and last_status_change columns to agents table (PostgreSQL)")


def downgrade() -> None:
    """Remove health_score and last_status_change columns from agents table."""
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        # Recreate table without health columns
        try:
            op.execute(sa.text("ALTER TABLE agents RENAME TO agents_with_health"))
            op.create_table(
                "agents",
                sa.Column("id", sa.String(36), primary_key=True, nullable=False),
                sa.Column("agent_id", sa.String(128), nullable=False, unique=True, index=True),
                sa.Column("credential", sa.String(128), nullable=False, unique=True, index=True),
                sa.Column("hostname", sa.String(256), nullable=False),
                sa.Column("ip_address", sa.String()),
                sa.Column("os_version", sa.String(64), nullable=False),
                sa.Column("kernel_version", sa.String(64)),
                sa.Column("agent_version", sa.String(32), nullable=False),
                sa.Column("cpu_cores", sa.Integer(), nullable=False),
                sa.Column("total_memory", sa.BigInteger(), nullable=False),
                sa.Column("disk_total", sa.BigInteger()),
                sa.Column("status", sa.String(20), nullable=False, server_default="offline", index=True),
                sa.Column("last_heartbeat", sa.DateTime(timezone=True), index=True),
                sa.Column("last_heartbeat_ip", sa.String()),
                sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
                sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
                sa.Column("tags", sa.JSON(), server_default="[]"),
                sa.Column("metadata", sa.JSON(), server_default="{}"),
                sa.Column("config_version", sa.Integer(), server_default="0"),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
                sa.Column("is_deleted", sa.Boolean(), server_default="0", nullable=False),
                sa.Column("deleted_at", sa.DateTime(timezone=True)),
            )
            op.execute(sa.text(
                "INSERT INTO agents (id, agent_id, credential, hostname, ip_address, os_version, "
                "kernel_version, agent_version, cpu_cores, total_memory, disk_total, status, "
                "last_heartbeat, last_heartbeat_ip, registered_at, first_seen_at, tags, metadata, "
                "config_version, created_at, updated_at, is_deleted, deleted_at) "
                "SELECT id, agent_id, credential, hostname, ip_address, os_version, "
                "kernel_version, agent_version, cpu_cores, total_memory, disk_total, status, "
                "last_heartbeat, last_heartbeat_ip, registered_at, first_seen_at, tags, metadata, "
                "config_version, created_at, updated_at, is_deleted, deleted_at "
                "FROM agents_with_health"
            ))
            op.drop_table("agents_with_health")
        except Exception as e:
            print(f"Downgrade error: {e}")
    else:
        op.drop_column("agents", "last_status_change")
        op.drop_column("agents", "health_score")
