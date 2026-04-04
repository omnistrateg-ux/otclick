"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01

Creates all tables for Otclick Employer Acquisition Engine.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Outreach campaigns (must be created first for FK)
    op.create_table(
        "outreach_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("segment_filter", sa.String(50)),
        sa.Column("min_score", sa.Float),
        sa.Column("max_daily_emails", sa.Integer, default=50),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("paused_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime),
    )

    # Employer leads
    op.create_table(
        "employer_leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_name", sa.String(500), nullable=False),
        sa.Column("domain", sa.String(255)),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_url", sa.String(2000)),
        sa.Column("status", sa.String(50), nullable=False, server_default="lead_found"),
        sa.Column("status_changed_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("status_history", postgresql.JSON, server_default="[]"),
        sa.Column("city", sa.String(100)),
        sa.Column("region", sa.String(100)),
        sa.Column("company_profile_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("outreach_campaigns.id"),
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Column("archived_at", sa.DateTime),
        sa.Column("archived_reason", sa.String(100)),
        sa.Column("opted_out", sa.Boolean, default=False),
        sa.Column("opted_out_at", sa.DateTime),
        sa.Column("do_not_contact_until", sa.DateTime),
    )
    op.create_index("ix_employer_leads_status", "employer_leads", ["status"])
    op.create_index("ix_employer_leads_domain", "employer_leads", ["domain"])

    # Company profiles
    op.create_table(
        "company_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employer_leads.id"),
            unique=True,
        ),
        sa.Column("legal_name", sa.String(500)),
        sa.Column("brand_name", sa.String(500)),
        sa.Column("inn", sa.String(12), index=True),
        sa.Column("domain", sa.String(255), index=True),
        sa.Column("website_url", sa.String(2000)),
        sa.Column("industry", sa.String(50), server_default="other"),
        sa.Column("sub_industry", sa.String(100)),
        sa.Column("employee_count", sa.Integer),
        sa.Column("employee_count_source", sa.String(50)),
        sa.Column("city", sa.String(100)),
        sa.Column("region", sa.String(100)),
        sa.Column("branches_count", sa.Integer),
        sa.Column("cities_presence", postgresql.JSON, server_default="[]"),
        sa.Column("active_vacancies_count", sa.Integer),
        sa.Column("hiring_intensity", sa.String(20), server_default="low"),
        sa.Column("vacancy_sources", postgresql.JSON, server_default="[]"),
        sa.Column("typical_roles", postgresql.JSON, server_default="[]"),
        sa.Column("avg_vacancy_age_days", sa.Float),
        sa.Column("has_hr_department", sa.Boolean),
        sa.Column("pain_points", postgresql.JSON, server_default="[]"),
        sa.Column("personalization_hooks", postgresql.JSON, server_default="[]"),
        sa.Column("recent_news", postgresql.JSON, server_default="[]"),
        sa.Column("enriched_at", sa.DateTime),
        sa.Column("enrichment_source", sa.String(50)),
    )

    # Add FK from employer_leads to company_profiles
    op.create_foreign_key(
        "fk_employer_leads_company_profile",
        "employer_leads",
        "company_profiles",
        ["company_profile_id"],
        ["id"],
    )

    # Employer contacts
    op.create_table(
        "employer_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employer_leads.id"),
        ),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100)),
        sa.Column("last_name", sa.String(100)),
        sa.Column("role", sa.String(50), server_default="other"),
        sa.Column("job_title", sa.String(200)),
        sa.Column("email", sa.String(255), index=True),
        sa.Column("email_verified", sa.Boolean, default=False),
        sa.Column("email_verification_date", sa.DateTime),
        sa.Column("phone", sa.String(50)),
        sa.Column("linkedin_url", sa.String(500)),
        sa.Column("telegram", sa.String(100)),
        sa.Column("is_primary", sa.Boolean, default=False),
        sa.Column("contact_source", sa.String(50)),
        sa.Column("opted_out", sa.Boolean, default=False),
        sa.Column("bounce_count", sa.Integer, default=0),
        sa.Column("last_bounce_at", sa.DateTime),
    )

    # Lead scores
    op.create_table(
        "lead_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employer_leads.id"),
        ),
        sa.Column("total_score", sa.Float, nullable=False),
        sa.Column("hiring_intensity_score", sa.Float, nullable=False),
        sa.Column("industry_fit_score", sa.Float, nullable=False),
        sa.Column("contact_quality_score", sa.Float, nullable=False),
        sa.Column("company_size_score", sa.Float, nullable=False),
        sa.Column("recency_score", sa.Float, nullable=False),
        sa.Column("scoring_model_version", sa.String(20), server_default="v1"),
        sa.Column("reasoning", sa.Text),
        sa.Column("scored_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Lead segments
    op.create_table(
        "lead_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employer_leads.id"),
        ),
        sa.Column("segment", sa.String(50), nullable=False),
        sa.Column("sub_segment", sa.String(100)),
        sa.Column("communication_angle", sa.String(50), nullable=False),
        sa.Column("tone", sa.String(50), nullable=False),
        sa.Column("offer_type", sa.String(50), nullable=False),
        sa.Column("priority", sa.String(20), server_default="normal"),
        sa.Column("pain_statement", sa.Text, nullable=False),
        sa.Column("value_proposition", sa.Text, nullable=False),
        sa.Column("proof_point", sa.Text, nullable=False),
        sa.Column("suggested_cta", sa.String(255), nullable=False),
    )

    # Email sequences
    op.create_table(
        "email_sequences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employer_leads.id"),
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employer_contacts.id"),
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("outreach_campaigns.id"),
        ),
        sa.Column("current_step", sa.Integer, default=0),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("completed_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_email_at", sa.DateTime),
        sa.Column("next_email_at", sa.DateTime),
    )

    # Email messages
    op.create_table(
        "email_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "sequence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_sequences.id"),
        ),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employer_leads.id"),
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employer_contacts.id"),
        ),
        sa.Column("email_type", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("step_number", sa.Integer, nullable=False),
        sa.Column("generation_model", sa.String(100)),
        sa.Column("generation_prompt_version", sa.String(20)),
        sa.Column("quality_gate_passed", sa.Boolean, default=False),
        sa.Column("quality_gate_issues", postgresql.JSON, server_default="[]"),
        sa.Column("sent_at", sa.DateTime),
        sa.Column("message_id_header", sa.String(255)),
        sa.Column("delivered", sa.Boolean),
        sa.Column("bounced", sa.Boolean),
        sa.Column("bounce_type", sa.String(20)),
        sa.Column("bounce_reason", sa.Text),
        sa.Column("opened", sa.Boolean),
        sa.Column("opened_at", sa.DateTime),
        sa.Column("open_count", sa.Integer, default=0),
        sa.Column("clicked", sa.Boolean),
        sa.Column("replied", sa.Boolean),
        sa.Column("replied_at", sa.DateTime),
        sa.Column("reply_text", sa.Text),
    )
    op.create_index("ix_email_messages_sent_at", "email_messages", ["sent_at"])

    # Lead signals
    op.create_table(
        "lead_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employer_leads.id"),
        ),
        sa.Column(
            "email_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_messages.id"),
        ),
        sa.Column("intent", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Float, default=1.0),
        sa.Column("raw_text", sa.Text),
        sa.Column("analyzed_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("analysis_model", sa.String(100)),
    )

    # Lead qualifications
    op.create_table(
        "lead_qualifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employer_leads.id"),
        ),
        sa.Column("is_qualified", sa.Boolean, nullable=False),
        sa.Column("qualification_reason", sa.Text, nullable=False),
        sa.Column("signals", postgresql.JSON, server_default="[]"),
        sa.Column("qualified_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("qualified_by", sa.String(100)),
    )

    # Manager handoffs
    op.create_table(
        "manager_handoffs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employer_leads.id"),
        ),
        sa.Column(
            "qualification_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lead_qualifications.id"),
        ),
        sa.Column("company_name", sa.String(500), nullable=False),
        sa.Column("contact_name", sa.String(255), nullable=False),
        sa.Column("contact_email", sa.String(255)),
        sa.Column("contact_phone", sa.String(50)),
        sa.Column("contact_role", sa.String(100), nullable=False),
        sa.Column("segment", sa.String(50), nullable=False),
        sa.Column("city", sa.String(100)),
        sa.Column("company_size", sa.String(50)),
        sa.Column("hiring_intensity", sa.String(20)),
        sa.Column("why_this_lead_matters", sa.Text, nullable=False),
        sa.Column("lead_score", sa.Float, nullable=False),
        sa.Column("interest_signals", postgresql.JSON, server_default="[]"),
        sa.Column("emails_sent_summary", postgresql.JSON, server_default="[]"),
        sa.Column("employer_reply_summary", sa.Text),
        sa.Column("conversation_history", sa.Text),
        sa.Column("suggested_next_step", sa.Text, nullable=False),
        sa.Column("talking_points", postgresql.JSON, server_default="[]"),
        sa.Column("manager_id", sa.String(100)),
        sa.Column("notified_via", sa.String(20)),
        sa.Column("notified_at", sa.DateTime),
        sa.Column("accepted_at", sa.DateTime),
        sa.Column("call_scheduled_at", sa.DateTime),
        sa.Column("call_result", sa.String(50)),
    )

    # Domain events
    op.create_table(
        "domain_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), index=True),
        sa.Column("event_type", sa.String(50), nullable=False, index=True),
        sa.Column("payload", postgresql.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), index=True),
        sa.Column("processed", sa.Boolean, default=False, index=True),
        sa.Column("processed_at", sa.DateTime),
    )


def downgrade() -> None:
    op.drop_table("domain_events")
    op.drop_table("manager_handoffs")
    op.drop_table("lead_qualifications")
    op.drop_table("lead_signals")
    op.drop_table("email_messages")
    op.drop_table("email_sequences")
    op.drop_table("lead_segments")
    op.drop_table("lead_scores")
    op.drop_table("employer_contacts")
    op.drop_constraint(
        "fk_employer_leads_company_profile", "employer_leads", type_="foreignkey"
    )
    op.drop_table("company_profiles")
    op.drop_table("employer_leads")
    op.drop_table("outreach_campaigns")
