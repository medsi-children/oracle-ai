"""mark repeatable marketplace items

Revision ID: 0004_repeatable_items
Revises: 0003_group_economy_and_stars
Create Date: 2026-05-10 17:10:00
"""

from __future__ import annotations

from alembic import op

revision = "0004_repeatable_items"
down_revision = "0003_group_economy_and_stars"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE alembic_version
        ALTER COLUMN version_num TYPE VARCHAR(64)
        """
    )
    op.execute(
        """
        ALTER TABLE marketplace_items
        ADD COLUMN IF NOT EXISTS is_repeatable BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    op.execute(
        """
        UPDATE marketplace_items
        SET is_repeatable = TRUE
        WHERE item_type = 'wisdom_sphere'
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE marketplace_items DROP COLUMN IF EXISTS is_repeatable")
