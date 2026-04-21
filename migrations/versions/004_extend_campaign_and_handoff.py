"""Extend campaign and handoff tables

Revision ID: 004
Revises: 003
Create Date: 2025-04-21

Adds missing fields to outreach_campaigns and manager_handoffs tables
to support full API functionality and persistent storage.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extend outreach_campaigns table
    op.add_column(
        "outreach_campaigns",
        sa.Column("daily_discovery_limit", sa.Integer(), server_default="100"),
    )
    op.add_column(
        "outreach_campaigns",
        sa.Column("industries", JSON(), server_default="[]"),
    )
    op.add_column(
        "outreach_campaigns",
        sa.Column("regions", JSON(), server_default="[]"),
    )
    op.add_column(
        "outreach_campaigns",
        sa.Column("status", sa.String(20), server_default="draft"),
    )
    op.add_column(
        "outreach_campaigns",
        sa.Column("leads_discovered", sa.Integer(), server_default="0"),
    )
    op.add_column(
        "outreach_campaigns",
        sa.Column("leads_qualified", sa.Integer(), server_default="0"),
    )
    op.add_column(
        "outreach_campaigns",
        sa.Column("leads_converted", sa.Integer(), server_default="0"),
    )
    op.add_column(
        "outreach_campaigns",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # Extend manager_handoffs table
    op.add_column(
        "manager_handoffs",
        sa.Column("status", sa.String(20), server_default="pending"),
    )
    op.add_column(
        "manager_handoffs",
        sa.Column("priority", sa.String(20), server_default="normal"),
    )
    op.add_column(
        "manager_handoffs",
        sa.Column("notes", sa.Text()),
    )
    op.add_column(
        "manager_handoffs",
        sa.Column("rejected_at", sa.DateTime()),
    )
    op.add_column(
        "manager_handoffs",
        sa.Column("rejection_reason", sa.Text()),
    )
    op.add_column(
        "manager_handoffs",
        sa.Column("completed_at", sa.DateTime()),
    )
    op.add_column(
        "manager_handoffs",
        sa.Column("outcome", sa.Text()),
    )
    op.add_column(
        "manager_handoffs",
        sa.Column("deal_value", sa.Float()),
    )
    op.add_column(
        "manager_handoffs",
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Make qualification_id nullable
    op.alter_column(
        "manager_handoffs",
        "qualification_id",
        existing_type=sa.dialects.postgresql.UUID(),
        nullable=True,
    )

    # Make some fields nullable that were previously required
    op.alter_column(
        "manager_handoffs",
        "contact_name",
        existing_type=sa.String(255),
        nullable=True,
    )
    op.alter_column(
        "manager_handoffs",
        "contact_role",
        existing_type=sa.String(100),
        nullable=True,
    )
    op.alter_column(
        "manager_handoffs",
        "segment",
        existing_type=sa.String(50),
        nullable=True,
    )
    op.alter_column(
        "manager_handoffs",
        "why_this_lead_matters",
        existing_type=sa.Text(),
        nullable=True,
    )
    op.alter_column(
        "manager_handoffs",
        "lead_score",
        existing_type=sa.Float(),
        nullable=True,
    )
    op.alter_column(
        "manager_handoffs",
        "suggested_next_step",
        existing_type=sa.Text(),
        nullable=True,
    )


def downgrade() -> None:
    # Remove columns from manager_handoffs
    op.drop_column("manager_handoffs", "created_at")
    op.drop_column("manager_handoffs", "deal_value")
    op.drop_column("manager_handoffs", "outcome")
    op.drop_column("manager_handoffs", "completed_at")
    op.drop_column("manager_handoffs", "rejection_reason")
    op.drop_column("manager_handoffs", "rejected_at")
    op.drop_column("manager_handoffs", "notes")
    op.drop_column("manager_handoffs", "priority")
    op.drop_column("manager_handoffs", "status")

    # Remove columns from outreach_campaigns
    op.drop_column("outreach_campaigns", "updated_at")
    op.drop_column("outreach_campaigns", "leads_converted")
    op.drop_column("outreach_campaigns", "leads_qualified")
    op.drop_column("outreach_campaigns", "leads_discovered")
    op.drop_column("outreach_campaigns", "status")
    op.drop_column("outreach_campaigns", "regions")
    op.drop_column("outreach_campaigns", "industries")
    op.drop_column("outreach_campaigns", "daily_discovery_limit")

    # Revert nullable changes
    op.alter_column(
        "manager_handoffs",
        "qualification_id",
        existing_type=sa.dialects.postgresql.UUID(),
        nullable=False,
    )
    op.alter_column(
        "manager_handoffs",
        "contact_name",
        existing_type=sa.String(255),
        nullable=False,
    )
    op.alter_column(
        "manager_handoffs",
        "contact_role",
        existing_type=sa.String(100),
        nullable=False,
    )
    op.alter_column(
        "manager_handoffs",
        "segment",
        existing_type=sa.String(50),
        nullable=False,
    )
    op.alter_column(
        "manager_handoffs",
        "why_this_lead_matters",
        existing_type=sa.Text(),
        nullable=False,
    )
    op.alter_column(
        "manager_handoffs",
        "lead_score",
        existing_type=sa.Float(),
        nullable=False,
    )
    op.alter_column(
        "manager_handoffs",
        "suggested_next_step",
        existing_type=sa.Text(),
        nullable=False,
    )
