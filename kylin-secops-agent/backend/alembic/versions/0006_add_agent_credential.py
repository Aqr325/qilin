"""add credential column to agents table

Revision ID: 0006_add_agent_credential
Revises: 0005_fix_audit_login_pk_to_uuid
Create Date: 2026-07-04 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "0006_add_agent_credential"
down_revision = "0005_fix_audit_login_pk_to_uuid"
branch_labels = None
depends_on = None


def upgrade():
    """Add credential column to agents table."""
    # Check if credential column already exists (for idempotency)
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        # SQLite doesn't support ALTER TABLE ADD COLUMN with constraints well,
        # so we recreate the table
        # Get existing data
        try:
            result = conn.execute(sa.text(
                "SELECT sql FROM sqlite_master WHERE name='agents' AND type='table'"
            )).fetchone()
            if result and 'credential' not in (result[0] or ''):
                # Rename old table
                op.execute(sa.text("ALTER TABLE agents RENAME TO agents_old"))
                # Create new table with credential column
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
                # Copy data from old table (credential gets empty string, will be overwritten on next heartbeat)
                op.execute(sa.text(
                    "INSERT INTO agents (id, agent_id, credential, hostname, ip_address, os_version, "
                    "kernel_version, agent_version, cpu_cores, total_memory, disk_total, status, "
                    "last_heartbeat, last_heartbeat_ip, registered_at, first_seen_at, tags, metadata, "
                    "config_version, created_at, updated_at, is_deleted, deleted_at) "
                    "SELECT id, agent_id, '', hostname, ip_address, os_version, "
                    "kernel_version, agent_version, cpu_cores, total_memory, disk_total, status, "
                    "last_heartbeat, last_heartbeat_ip, registered_at, first_seen_at, tags, metadata, "
                    "config_version, created_at, updated_at, is_deleted, deleted_at "
                    "FROM agents_old"
                ))
                op.drop_table("agents_old")
                print("Added credential column to agents table (SQLite)")
            else:
                print("credential column already exists (SQLite)")
        except Exception as e:
            print(f"Migration check: {e}")
    else:
        # PostgreSQL - simpler ALTER TABLE
        op.add_column(
            "agents",
            sa.Column(
                "credential",
                sa.String(128),
                nullable=False,
                server_default="",
                comment="Agent认证凭据",
                unique=True,
            ),
        )
        op.create_index(op.f("ix_agents_credential"), "agents", ["credential"], unique=True)
        print("Added credential column to agents table (PostgreSQL)")


def downgrade():
    """Remove credential column from agents table."""
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        # Recreate table without credential
        try:
            op.execute(sa.text("ALTER TABLE agents RENAME TO agents_with_cred"))
            op.create_table(
                "agents",
                sa.Column("id", sa.String(36), primary_key=True, nullable=False),
                sa.Column("agent_id", sa.String(128), nullable=False, unique=True, index=True),
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
                "INSERT INTO agents (id, agent_id, hostname, ip_address, os_version, "
                "kernel_version, agent_version, cpu_cores, total_memory, disk_total, status, "
                "last_heartbeat, last_heartbeat_ip, registered_at, first_seen_at, tags, metadata, "
                "config_version, created_at, updated_at, is_deleted, deleted_at) "
                "SELECT id, agent_id, hostname, ip_address, os_version, "
                "kernel_version, agent_version, cpu_cores, total_memory, disk_total, status, "
                "last_heartbeat, last_heartbeat_ip, registered_at, first_seen_at, tags, metadata, "
                "config_version, created_at, updated_at, is_deleted, deleted_at "
                "FROM agents_with_cred"
            ))
            op.drop_table("agents_with_cred")
        except Exception as e:
            print(f"Downgrade error: {e}")
    else:
        op.drop_index(op.f("ix_agents_credential"), table_name="agents")
        op.drop_column("agents", "credential")