"""SQLAlchemy ORM models."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class EmployerLeadDB(Base):
    """ORM model for employer leads."""

    __tablename__ = "employer_leads"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_name: Mapped[str] = mapped_column(String(500), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2000))

    # Lifecycle
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="lead_found")
    status_changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status_history: Mapped[list] = mapped_column(JSON, default=list)

    # Geography
    city: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))

    # Vacancy info (from discovery)
    vacancy: Mapped[str | None] = mapped_column(String(500))

    # Foreign Keys
    company_profile_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company_profiles.id")
    )
    campaign_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("outreach_campaigns.id")
    )

    # Meta
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_reason: Mapped[str | None] = mapped_column(String(100))

    # Compliance
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime)
    do_not_contact_until: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships - explicit foreign_keys to avoid ambiguity
    company_profile: Mapped["CompanyProfileDB | None"] = relationship(
        "CompanyProfileDB",
        back_populates="lead",
        uselist=False,
        foreign_keys="CompanyProfileDB.lead_id",
    )
    contacts: Mapped[list["EmployerContactDB"]] = relationship(
        "EmployerContactDB",
        back_populates="lead",
        foreign_keys="EmployerContactDB.lead_id",
    )
    scores: Mapped[list["LeadScoreDB"]] = relationship(
        "LeadScoreDB",
        back_populates="lead",
        foreign_keys="LeadScoreDB.lead_id",
    )
    segments: Mapped[list["LeadSegmentDB"]] = relationship(
        "LeadSegmentDB",
        back_populates="lead",
        foreign_keys="LeadSegmentDB.lead_id",
    )
    sequences: Mapped[list["EmailSequenceDB"]] = relationship(
        "EmailSequenceDB",
        back_populates="lead",
        foreign_keys="EmailSequenceDB.lead_id",
    )
    signals: Mapped[list["LeadSignalDB"]] = relationship(
        "LeadSignalDB",
        back_populates="lead",
        foreign_keys="LeadSignalDB.lead_id",
    )


class CompanyProfileDB(Base):
    """ORM model for company profiles."""

    __tablename__ = "company_profiles"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employer_leads.id"), unique=True
    )

    # Basic data
    legal_name: Mapped[str | None] = mapped_column(String(500))
    brand_name: Mapped[str | None] = mapped_column(String(500))
    inn: Mapped[str | None] = mapped_column(String(12), index=True)
    domain: Mapped[str | None] = mapped_column(String(255), index=True)
    website_url: Mapped[str | None] = mapped_column(String(2000))

    # Classification
    industry: Mapped[str] = mapped_column(String(50), default="other")
    sub_industry: Mapped[str | None] = mapped_column(String(100))
    employee_count: Mapped[int | None] = mapped_column(Integer)
    employee_count_source: Mapped[str | None] = mapped_column(String(50))

    # Geography
    city: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    branches_count: Mapped[int | None] = mapped_column(Integer)
    cities_presence: Mapped[list] = mapped_column(JSON, default=list)

    # Hiring signals
    active_vacancies_count: Mapped[int | None] = mapped_column(Integer)
    hiring_intensity: Mapped[str] = mapped_column(String(20), default="low")
    vacancy_sources: Mapped[list] = mapped_column(JSON, default=list)
    typical_roles: Mapped[list] = mapped_column(JSON, default=list)
    avg_vacancy_age_days: Mapped[float | None] = mapped_column(Float)
    has_hr_department: Mapped[bool | None] = mapped_column(Boolean)

    # Personalization context
    pain_points: Mapped[list] = mapped_column(JSON, default=list)
    personalization_hooks: Mapped[list] = mapped_column(JSON, default=list)
    recent_news: Mapped[list] = mapped_column(JSON, default=list)

    # Timestamps
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime)
    enrichment_source: Mapped[str | None] = mapped_column(String(50))

    # Relationships
    lead: Mapped["EmployerLeadDB"] = relationship(
        "EmployerLeadDB",
        back_populates="company_profile",
        foreign_keys=[lead_id],
    )


class EmployerContactDB(Base):
    """ORM model for employer contacts."""

    __tablename__ = "employer_contacts"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employer_leads.id"))

    # Personal data
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))

    # Role
    role: Mapped[str] = mapped_column(String(50), default="other")
    job_title: Mapped[str | None] = mapped_column(String(200))

    # Contact channels
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verification_date: Mapped[datetime | None] = mapped_column(DateTime)
    phone: Mapped[str | None] = mapped_column(String(50))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    telegram: Mapped[str | None] = mapped_column(String(100))

    # Priority
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    contact_source: Mapped[str | None] = mapped_column(String(50))

    # Compliance
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)
    bounce_count: Mapped[int] = mapped_column(Integer, default=0)
    last_bounce_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    lead: Mapped["EmployerLeadDB"] = relationship(
        "EmployerLeadDB",
        back_populates="contacts",
        foreign_keys=[lead_id],
    )
    sequences: Mapped[list["EmailSequenceDB"]] = relationship(
        "EmailSequenceDB",
        back_populates="contact",
        foreign_keys="EmailSequenceDB.contact_id",
    )


class LeadScoreDB(Base):
    """ORM model for lead scores."""

    __tablename__ = "lead_scores"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employer_leads.id"))

    # Total score
    total_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Components
    hiring_intensity_score: Mapped[float] = mapped_column(Float, nullable=False)
    industry_fit_score: Mapped[float] = mapped_column(Float, nullable=False)
    contact_quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    company_size_score: Mapped[float] = mapped_column(Float, nullable=False)
    recency_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Meta
    scoring_model_version: Mapped[str] = mapped_column(String(20), default="v1")
    reasoning: Mapped[str | None] = mapped_column(Text)
    scored_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    lead: Mapped["EmployerLeadDB"] = relationship(
        "EmployerLeadDB",
        back_populates="scores",
        foreign_keys=[lead_id],
    )


class LeadSegmentDB(Base):
    """ORM model for lead segments."""

    __tablename__ = "lead_segments"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employer_leads.id"))

    # Segment
    segment: Mapped[str] = mapped_column(String(50), nullable=False)
    sub_segment: Mapped[str | None] = mapped_column(String(100))

    # Communication strategy
    communication_angle: Mapped[str] = mapped_column(String(50), nullable=False)
    tone: Mapped[str] = mapped_column(String(50), nullable=False)
    offer_type: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="normal")

    # Email content
    pain_statement: Mapped[str] = mapped_column(Text, nullable=False)
    value_proposition: Mapped[str] = mapped_column(Text, nullable=False)
    proof_point: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_cta: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    lead: Mapped["EmployerLeadDB"] = relationship(
        "EmployerLeadDB",
        back_populates="segments",
        foreign_keys=[lead_id],
    )


class OutreachCampaignDB(Base):
    """ORM model for outreach campaigns."""

    __tablename__ = "outreach_campaigns"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Settings
    segment_filter: Mapped[str | None] = mapped_column(String(50))
    min_score: Mapped[float | None] = mapped_column(Float)
    max_daily_emails: Mapped[int] = mapped_column(Integer, default=50)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)


class EmailSequenceDB(Base):
    """ORM model for email sequences."""

    __tablename__ = "email_sequences"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employer_leads.id"))
    contact_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employer_contacts.id")
    )
    campaign_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("outreach_campaigns.id")
    )

    # Status
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_email_at: Mapped[datetime | None] = mapped_column(DateTime)
    next_email_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    lead: Mapped["EmployerLeadDB"] = relationship(
        "EmployerLeadDB",
        back_populates="sequences",
        foreign_keys=[lead_id],
    )
    contact: Mapped["EmployerContactDB"] = relationship(
        "EmployerContactDB",
        back_populates="sequences",
        foreign_keys=[contact_id],
    )
    messages: Mapped[list["EmailMessageDB"]] = relationship(
        "EmailMessageDB",
        back_populates="sequence",
        foreign_keys="EmailMessageDB.sequence_id",
    )


class EmailMessageDB(Base):
    """ORM model for email messages."""

    __tablename__ = "email_messages"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    sequence_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_sequences.id")
    )
    lead_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employer_leads.id"))
    contact_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employer_contacts.id")
    )

    # Content
    email_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Generation
    generation_model: Mapped[str | None] = mapped_column(String(100))
    generation_prompt_version: Mapped[str | None] = mapped_column(String(20))
    quality_gate_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    quality_gate_issues: Mapped[list] = mapped_column(JSON, default=list)

    # Delivery
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    message_id_header: Mapped[str | None] = mapped_column(String(255))
    delivered: Mapped[bool | None] = mapped_column(Boolean)
    bounced: Mapped[bool | None] = mapped_column(Boolean)
    bounce_type: Mapped[str | None] = mapped_column(String(20))
    bounce_reason: Mapped[str | None] = mapped_column(Text)

    # Tracking
    opened: Mapped[bool | None] = mapped_column(Boolean)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime)
    open_count: Mapped[int] = mapped_column(Integer, default=0)
    clicked: Mapped[bool | None] = mapped_column(Boolean)

    # Reply
    replied: Mapped[bool | None] = mapped_column(Boolean)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime)
    reply_text: Mapped[str | None] = mapped_column(Text)

    # Relationships
    sequence: Mapped["EmailSequenceDB"] = relationship(
        "EmailSequenceDB",
        back_populates="messages",
        foreign_keys=[sequence_id],
    )


class LeadSignalDB(Base):
    """ORM model for lead signals."""

    __tablename__ = "lead_signals"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employer_leads.id"))
    email_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_messages.id")
    )

    # Signal
    intent: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    raw_text: Mapped[str | None] = mapped_column(Text)

    # Analysis
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    analysis_model: Mapped[str | None] = mapped_column(String(100))

    # Relationships
    lead: Mapped["EmployerLeadDB"] = relationship(
        "EmployerLeadDB",
        back_populates="signals",
        foreign_keys=[lead_id],
    )


class LeadQualificationDB(Base):
    """ORM model for lead qualifications."""

    __tablename__ = "lead_qualifications"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employer_leads.id"))

    # Decision
    is_qualified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    qualification_reason: Mapped[str] = mapped_column(Text, nullable=False)
    signals: Mapped[list] = mapped_column(JSON, default=list)

    # Meta
    qualified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    qualified_by: Mapped[str | None] = mapped_column(String(100))


class ManagerHandoffDB(Base):
    """ORM model for manager handoffs."""

    __tablename__ = "manager_handoffs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employer_leads.id"))
    qualification_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lead_qualifications.id")
    )

    # Who
    company_name: Mapped[str] = mapped_column(String(500), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(50))
    contact_role: Mapped[str] = mapped_column(String(100), nullable=False)

    # Context
    segment: Mapped[str] = mapped_column(String(50), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100))
    company_size: Mapped[str | None] = mapped_column(String(50))
    hiring_intensity: Mapped[str | None] = mapped_column(String(20))

    # Why important
    why_this_lead_matters: Mapped[str] = mapped_column(Text, nullable=False)
    lead_score: Mapped[float] = mapped_column(Float, nullable=False)

    # What happened
    interest_signals: Mapped[list] = mapped_column(JSON, default=list)
    emails_sent_summary: Mapped[list] = mapped_column(JSON, default=list)
    employer_reply_summary: Mapped[str | None] = mapped_column(Text)
    conversation_history: Mapped[str | None] = mapped_column(Text)

    # Recommendation
    suggested_next_step: Mapped[str] = mapped_column(Text, nullable=False)
    talking_points: Mapped[list] = mapped_column(JSON, default=list)

    # Handoff status
    manager_id: Mapped[str | None] = mapped_column(String(100))
    notified_via: Mapped[str | None] = mapped_column(String(20))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime)
    call_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    call_result: Mapped[str | None] = mapped_column(String(50))


class DomainEventDB(Base):
    """ORM model for domain events."""

    __tablename__ = "domain_events"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    # Meta
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)
