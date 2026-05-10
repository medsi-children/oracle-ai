"""mark repeatable marketplace items

Revision ID: 0004_marketplace_repeatable_items
Revises: 0003_group_economy_and_stars
Create Date: 2026-05-10 17:10:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_marketplace_repeatable_items"
down_revision = "0003_group_economy_and_stars"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "marketplace_items",
        sa.Column("is_repeatable", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        """
        UPDATE marketplace_items
        SET is_repeatable = TRUE
        WHERE item_type = 'wisdom_sphere'
        """
    )


def downgrade() -> None:
    op.drop_column("marketplace_items", "is_repeatable")
