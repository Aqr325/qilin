"""0001_initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-06-23 20:00:00.000000
"""
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    # 1. Enable extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # 2. Create updated_at trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 3. Create roles table
    op.create_table("roles",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("idx_roles_name", "roles", ["name"])
    op.execute("""
        CREATE TRIGGER update_roles_updated_at
            BEFORE UPDATE ON roles
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)

    # 4. Create permissions table
    op.create_table("permissions",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("idx_permissions_code", "permissions", ["code"], unique=True)
    op.create_index("idx_permissions_module", "permissions", ["module"])

    # 5. Create role_permissions table
    op.create_table("role_permissions",
        sa.Column("role_id", postgresql.UUID(), nullable=False),
        sa.Column("permission_id", postgresql.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    # 6. Create users table
    op.create_table("users",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(128), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.Column("is_locked", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("login_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_ip", postgresql.INET(), nullable=True),
        sa.Column("mfa_enabled", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column("mfa_secret", sa.String(64), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("idx_users_username", "users", ["username"], unique=True)
    op.create_index("idx_users_email", "users", ["email"], unique=True)
    op.execute("""
        CREATE TRIGGER update_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)

    # 7. Create user_roles table
    op.create_table("user_roles",
        sa.Column("user_id", postgresql.UUID(), nullable=False),
        sa.Column("role_id", postgresql.UUID(), nullable=False),
        sa.Column("granted_by", postgresql.UUID(), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )

    # 8. Create agents table
    op.create_table("agents",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agent_id", sa.String(128), nullable=False),
        sa.Column("hostname", sa.String(256), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("os_version", sa.String(64), nullable=False),
        sa.Column("kernel_version", sa.String(64), nullable=True),
        sa.Column("agent_version", sa.String(32), nullable=False),
        sa.Column("cpu_cores", sa.Integer(), nullable=False),
        sa.Column("total_memory", sa.BigInteger(), nullable=False),
        sa.Column("disk_total", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(20), server_default=sa.text("'offline'"), nullable=False),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_ip", postgresql.INET(), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("tags", postgresql.JSONB(), server_default=sa.text("'[]'"), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("config_version", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id"),
    )
    op.create_index("idx_agents_agent_id", "agents", ["agent_id"], unique=True)
    op.create_index("idx_agents_status", "agents", ["status"])

    # 9. Create agent_heartbeats table
    op.create_table("agent_heartbeats",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.String(128), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("cpu_usage", sa.REAL(), nullable=True),
        sa.Column("cpu_cores", sa.SmallInteger(), nullable=True),
        sa.Column("memory_total", sa.Integer(), nullable=True),
        sa.Column("memory_used", sa.Integer(), nullable=True),
        sa.Column("memory_percent", sa.REAL(), nullable=True),
        sa.Column("disk_json", postgresql.JSONB(), nullable=True),
        sa.Column("processes_total", sa.Integer(), nullable=True),
        sa.Column("processes_running", sa.Integer(), nullable=True),
        sa.Column("agent_version", sa.String(32), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_heartbeats_agent_time", "agent_heartbeats", ["agent_id", sa.text("received_at DESC")])

    # 10. Create alerts table
    op.create_table("alerts",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("alert_seq", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.String(128), nullable=False),
        sa.Column("alert_type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("detail", postgresql.JSONB(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("source", sa.String(32), server_default=sa.text("'agent'"), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'new'"), nullable=False),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mitre_technique_id", sa.String(32), nullable=True),
        sa.Column("mitre_tactic", sa.String(64), nullable=True),
        sa.Column("mitre_technique_name", sa.String(128), nullable=True),
        sa.Column("assignee_id", postgresql.UUID(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suppressed", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column("suppressed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suppress_reason", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(), nullable=True),
        sa.Column("correlation_key", sa.String(128), nullable=True),
        sa.Column("correlation_count", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("alert_count", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ),
    )
    op.create_index("idx_alerts_status", "alerts", ["status", sa.text("created_at DESC")])
    op.create_index("idx_alerts_severity", "alerts", ["severity", sa.text("created_at DESC")])
    op.create_index("idx_alerts_type", "alerts", ["alert_type", sa.text("created_at DESC")])
    op.create_index("idx_alerts_agent_id", "alerts", ["agent_id", sa.text("created_at DESC")])
    op.create_index("idx_alerts_created_at", "alerts", [sa.text("created_at DESC")])
    op.execute("""
        CREATE TRIGGER update_alerts_updated_at
            BEFORE UPDATE ON alerts
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)

    # 11. Create alert_status_history table
    op.create_table("alert_status_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("alert_id", postgresql.UUID(), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("operator_id", postgresql.UUID(), nullable=True),
        sa.Column("operator_name", sa.String(64), nullable=True),
        sa.Column("operation", sa.String(32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("source", sa.String(16), server_default=sa.text("'manual'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_alert_history_alert", "alert_status_history", ["alert_id", sa.text("created_at")])

    # 12. Create policies table
    op.create_table("policies",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("policy_type", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("rules", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("target_type", sa.String(20), server_default=sa.text("'all'"), nullable=False),
        sa.Column("target_value", postgresql.JSONB(), server_default=sa.text("'[]'"), nullable=True),
        sa.Column("priority", sa.Integer(), server_default=sa.text("100"), nullable=False),
        sa.Column("effective_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_template", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column("created_by", postgresql.UUID(), nullable=True),
        sa.Column("updated_by", postgresql.UUID(), nullable=True),
        sa.Column("deployed_version", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ),
    )
    op.create_index("idx_policies_status", "policies", ["status"])
    op.create_index("idx_policies_type", "policies", ["policy_type"])

    # 13. Create policy_versions table
    op.create_table("policy_versions",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("policy_id", postgresql.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("rules", postgresql.JSONB(), nullable=False),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("policy_id", "version"),
    )

    # 14. Create policy_targets table
    op.create_table("policy_targets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("policy_id", postgresql.UUID(), nullable=False),
        sa.Column("agent_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("deployed_version", sa.Integer(), nullable=True),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("policy_id", "agent_id"),
    )

    # 15. Create login_logs table
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

    # 16. Create audit_logs table
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

    # 17. Create ai_conversations table
    op.create_table("ai_conversations",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(), nullable=False),
        sa.Column("title", sa.String(256), nullable=True),
        sa.Column("messages", postgresql.JSONB(), nullable=False),
        sa.Column("context", postgresql.JSONB(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("related_alert_id", postgresql.UUID(), nullable=True),
        sa.Column("feedback_score", sa.SmallInteger(), nullable=True),
        sa.Column("feedback_comment", sa.Text(), nullable=True),
        sa.Column("token_usage", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("model_name", sa.String(64), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ),
        sa.ForeignKeyConstraint(["related_alert_id"], ["alerts.id"], ),
    )
    op.create_index("idx_ai_conv_user", "ai_conversations", ["user_id", sa.text("updated_at DESC")])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("ai_conversations")
    op.drop_table("audit_logs")
    op.drop_table("login_logs")
    op.drop_table("policy_targets")
    op.drop_table("policy_versions")
    op.drop_table("policies")
    op.drop_table("alert_status_history")
    op.drop_table("alerts")
    op.drop_table("agent_heartbeats")
    op.drop_table("agents")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")