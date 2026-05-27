"""add users.protection_mode

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-27 00:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "protection_mode",
            sa.String(16),
            nullable=False,
            server_default="full",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "protection_mode")
