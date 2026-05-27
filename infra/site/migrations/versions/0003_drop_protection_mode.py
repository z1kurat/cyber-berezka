"""drop users.protection_mode (rollback of protection-modes feature)

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-27 22:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("users", "protection_mode")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "protection_mode",
            sa.String(16),
            nullable=False,
            server_default="full",
        ),
    )
