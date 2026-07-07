"""add agent_tasks table for upgrade/restart task tracking

Revision ID: 0007_add_agent_tasks
Revises: 0006_add_agent_credential
Create Date: 2026-06-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "0007_add_agent_tasks"
down_revision = "0006_add_agent_credential"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create agent_tasks table (idempotent for both SQLite and PostgreSQL)."""
    # agent_tasks：Agent升级/重启等动作的可追踪任务记录
    op.execute(sa.text(
        """
        CREATE TABLE IF NOT EXISTS agent_tasks (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            agent_id VARCHAR(128) NOT NULL,
            task_type VARCHAR(20) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            params JSON,
            result JSON,
            error_message TEXT,
            created_by VARCHAR(36),
            completed_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_agent_tasks_agent_id ON agent_tasks (agent_id)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_agent_tasks_task_type ON agent_tasks (task_type)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_agent_tasks_status ON agent_tasks (status)"
    ))


def downgrade() -> None:
    """Drop agent_tasks table."""
    op.execute(sa.text("DROP TABLE IF EXISTS agent_tasks"))
