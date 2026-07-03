"""0003_add_alert_source_ip

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-24 22:00:00.000000
"""
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    # Add source_ip column to alerts table
    op.add_column("alerts",
        sa.Column("source_ip", sa.String(45), nullable=True, comment="来源IP地址")
    )
    op.create_index("idx_alerts_source_ip", "alerts", ["source_ip"])


def downgrade() -> None:
    op.drop_index("idx_alerts_source_ip", table_name="alerts")
    op.drop_column("alerts", "source_ip")
