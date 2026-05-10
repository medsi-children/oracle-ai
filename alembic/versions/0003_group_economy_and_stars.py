"""group economy and stars foundation

Revision ID: 0003_group_economy_and_stars
Revises: 0002_growth_modules
Create Date: 2026-05-10 15:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_group_economy_and_stars"
down_revision = "0002_growth_modules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("lifecycle_status", sa.String(length=64), nullable=False, server_default="newbie"),
    )
    op.execute(
        """
        UPDATE users
        SET lifecycle_status = 'beginner'
        WHERE profile_summary IS NOT NULL
           OR username = 'medsi_children'
           OR telegram_id = 7659888703
        """
    )

    op.add_column(
        "battles",
        sa.Column("entry_fee", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "battles",
        sa.Column("reward_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "battle_participants",
        sa.Column("entry_fee", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "group_discussions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True, index=True),
        sa.Column("discussion_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="active"),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "news_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("news_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "group_discussion_participants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "discussion_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("group_discussions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("entry_fee", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "star_payment_orders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("order_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="draft"),
        sa.Column("star_amount", sa.Integer(), nullable=False),
        sa.Column("token_amount", sa.Integer(), nullable=False),
        sa.Column("invoice_payload", sa.String(length=256), nullable=True, unique=True),
        sa.Column("telegram_payment_charge_id", sa.String(length=256), nullable=True, unique=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "star_withdrawal_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="pending"),
        sa.Column("token_amount", sa.Integer(), nullable=False),
        sa.Column("star_amount", sa.Integer(), nullable=False),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("star_withdrawal_requests")
    op.drop_table("star_payment_orders")
    op.drop_table("group_discussion_participants")
    op.drop_table("group_discussions")
    op.drop_column("battle_participants", "entry_fee")
    op.drop_column("battles", "reward_tokens")
    op.drop_column("battles", "entry_fee")
    op.drop_column("users", "lifecycle_status")
