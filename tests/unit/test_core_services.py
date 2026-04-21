"""Unit tests for core business services.

Tests for:
1. AnalyticsService - KPI and metrics
2. ComplianceService - Email compliance, opt-out, rate limiting
3. EmailService - Email sequence management
4. LeadService - Lead business logic
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

UTC = timezone.utc


# =============================================================================
# AnalyticsService Tests
# =============================================================================

class TestAnalyticsService:
    """Tests for analytics service."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        """Create analytics service with mock db."""
        from app.services.analytics_service import AnalyticsService
        return AnalyticsService(mock_db)

    @pytest.mark.asyncio
    async def test_get_funnel_metrics_defaults(self, service, mock_db):
        """Should return funnel metrics with default period."""
        # Mock all status count queries to return 0
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_db.execute.return_value = mock_result

        result = await service.get_funnel_metrics()

        assert result.period_start is not None
        assert result.period_end is not None
        assert result.discovered >= 0
        assert result.enriched >= 0
        assert result.converted >= 0
        # Default period is 7 days
        assert (result.period_end - result.period_start).days == 7

    @pytest.mark.asyncio
    async def test_get_funnel_metrics_with_dates(self, service, mock_db):
        """Should use provided date range."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_db.execute.return_value = mock_result

        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 31)

        result = await service.get_funnel_metrics(start_date=start, end_date=end)

        assert result.period_start == start
        assert result.period_end == end

    @pytest.mark.asyncio
    async def test_get_email_performance(self, service, mock_db):
        """Should calculate email performance metrics."""
        mock_result = MagicMock()
        # Return different values for different queries
        mock_result.scalar_one.side_effect = [100, 95, 5, 30, 0, 10]
        mock_db.execute.return_value = mock_result

        result = await service.get_email_performance()

        assert result.total_sent >= 0
        assert result.total_delivered >= 0
        assert 0 <= result.open_rate <= 1
        assert 0 <= result.reply_rate <= 1
        assert 0 <= result.bounce_rate <= 1

    @pytest.mark.asyncio
    async def test_get_email_performance_no_division_by_zero(self, service, mock_db):
        """Should handle zero emails without division error."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_db.execute.return_value = mock_result

        result = await service.get_email_performance()

        assert result.total_sent == 0
        assert result.open_rate == 0
        assert result.reply_rate == 0
        assert result.bounce_rate == 0

    @pytest.mark.asyncio
    async def test_get_time_series_discovered(self, service, mock_db):
        """Should return time series for discovered metric."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        mock_db.execute.return_value = mock_result

        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 3)

        result = await service.get_time_series("discovered", start, end, "day")

        assert len(result) == 2  # 2 days
        assert all("date" in point and "value" in point for point in result)

    @pytest.mark.asyncio
    async def test_get_reply_intent_distribution(self, service, mock_db):
        """Should return reply intent counts."""
        mock_result = MagicMock()
        mock_result.all.return_value = [("interested", 10), ("not_interested", 5)]
        mock_db.execute.return_value = mock_result

        result = await service.get_reply_intent_distribution()

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_handoff_metrics(self, service, mock_db):
        """Should return handoff metrics."""
        mock_result = MagicMock()
        mock_result.scalar_one.side_effect = [10, 8, 5, 75.0]
        mock_db.execute.return_value = mock_result

        result = await service.get_handoff_metrics()

        assert "total_handoffs" in result
        assert "accepted" in result
        assert "acceptance_rate" in result

    @pytest.mark.asyncio
    async def test_export_data(self, service, mock_db):
        """Should export all analytics data."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await service.export_data()

        assert "funnel" in result
        assert "email" in result
        assert "handoff" in result
        assert "generated_at" in result


# =============================================================================
# ComplianceService Tests
# =============================================================================

class TestComplianceService:
    """Tests for compliance service."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        """Create compliance service."""
        from app.services.compliance_service import ComplianceService
        return ComplianceService(mock_db)

    @pytest.fixture
    def sample_lead(self):
        """Create sample lead for testing."""
        from app.models.domain import EmployerLead
        return EmployerLead(
            company_name="Test Company",
            domain="test.ru",
            source="hh.ru",
        )

    @pytest.fixture
    def sample_contact(self, sample_lead):
        """Create sample contact."""
        from app.models.domain import EmployerContact
        from app.models.enums import ContactRole
        return EmployerContact(
            lead_id=sample_lead.id,
            full_name="Test Contact",
            role=ContactRole.HR_MANAGER,
            email="test@test.ru",
        )

    @pytest.mark.asyncio
    async def test_check_opt_out_not_opted_out(self, service, sample_lead, sample_contact):
        """Should return False if not opted out."""
        sample_lead.opted_out = False
        sample_contact.opted_out = False

        is_opted_out, reason = await service.check_opt_out(sample_lead, sample_contact)

        assert is_opted_out is False
        assert reason is None

    @pytest.mark.asyncio
    async def test_check_opt_out_lead_opted_out(self, service, sample_lead, sample_contact):
        """Should detect lead opt-out."""
        sample_lead.opted_out = True

        is_opted_out, reason = await service.check_opt_out(sample_lead, sample_contact)

        assert is_opted_out is True
        assert reason == "lead_opted_out"

    @pytest.mark.asyncio
    async def test_check_opt_out_contact_opted_out(self, service, sample_lead, sample_contact):
        """Should detect contact opt-out."""
        sample_lead.opted_out = False
        sample_contact.opted_out = True

        is_opted_out, reason = await service.check_opt_out(sample_lead, sample_contact)

        assert is_opted_out is True
        assert reason == "contact_opted_out"

    @pytest.mark.asyncio
    async def test_check_opt_out_in_cooldown(self, service, sample_lead, sample_contact):
        """Should detect lead in cooldown period."""
        sample_lead.opted_out = False
        sample_lead.do_not_contact_until = datetime.now(UTC) + timedelta(days=30)

        is_opted_out, reason = await service.check_opt_out(sample_lead, sample_contact)

        assert is_opted_out is True
        assert reason == "lead_in_cooldown"

    @pytest.mark.asyncio
    async def test_set_cooldown(self, service, sample_lead):
        """Should set cooldown period."""
        lead, cooldown_until = await service.set_cooldown(sample_lead, days=30)

        assert lead.do_not_contact_until is not None
        assert cooldown_until > datetime.now(UTC)
        expected_cooldown = datetime.now(UTC) + timedelta(days=30)
        assert abs((cooldown_until - expected_cooldown).total_seconds()) < 5

    @pytest.mark.asyncio
    async def test_check_rate_limit_sender_allowed(self, service):
        """Should allow when under limit."""
        result = await service.check_rate_limit_sender("sender@test.ru")

        assert result.allowed is True
        assert result.reason is None

    @pytest.mark.asyncio
    async def test_check_rate_limit_domain_allowed(self, service):
        """Should allow when under domain limit."""
        result = await service.check_rate_limit_domain("test.ru")

        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_can_send_email_all_checks_pass(self, service, sample_lead, sample_contact):
        """Should allow sending when all checks pass."""
        sample_lead.opted_out = False
        sample_contact.opted_out = False
        sample_contact.bounce_count = 0

        can_send, reason = await service.can_send_email(
            sample_lead, sample_contact, "sender@otclick.ru"
        )

        assert can_send is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_can_send_email_no_email(self, service, sample_lead, sample_contact):
        """Should reject if contact has no email."""
        sample_contact.email = None

        can_send, reason = await service.can_send_email(
            sample_lead, sample_contact, "sender@otclick.ru"
        )

        assert can_send is False
        assert reason == "no_contact_email"

    @pytest.mark.asyncio
    async def test_can_send_email_bounced_contact(self, service, sample_lead, sample_contact):
        """Should reject if contact has too many bounces."""
        sample_contact.bounce_count = 5

        can_send, reason = await service.can_send_email(
            sample_lead, sample_contact, "sender@otclick.ru"
        )

        assert can_send is False
        assert reason == "contact_bounced"

    @pytest.mark.asyncio
    async def test_process_hard_bounce(self, service, sample_contact):
        """Should process hard bounce."""
        initial_count = sample_contact.bounce_count

        await service.process_hard_bounce(sample_contact, "mailbox not found")

        assert sample_contact.bounce_count == initial_count + 1
        assert sample_contact.email_verified is False
        assert sample_contact.last_bounce_at is not None

    @pytest.mark.asyncio
    async def test_process_soft_bounce_retry(self, service, sample_contact):
        """Should allow retry on soft bounce."""
        sample_contact.bounce_count = 1

        should_retry = await service.process_soft_bounce(sample_contact, "mailbox full")

        assert should_retry is True
        assert sample_contact.bounce_count == 2

    @pytest.mark.asyncio
    async def test_process_soft_bounce_exceeded(self, service, sample_contact):
        """Should not retry after too many soft bounces."""
        sample_contact.bounce_count = 2

        should_retry = await service.process_soft_bounce(sample_contact, "mailbox full")

        assert should_retry is False

    def test_extract_domain(self, service):
        """Should extract domain from email."""
        assert service._extract_domain("user@example.com") == "example.com"
        assert service._extract_domain("user@SUB.Example.COM") == "sub.example.com"
        assert service._extract_domain("invalid") == ""

    def test_normalize_company_name(self, service):
        """Should normalize company names."""
        assert "ооо" not in service._normalize_company_name("ООО Рога и Копыта")
        assert "llc" not in service._normalize_company_name("Acme LLC")
        # Should preserve core name
        assert "рога" in service._normalize_company_name("ООО «Рога и Копыта»")


class TestWatchlist:
    """Tests for watchlist functions."""

    def test_is_on_watchlist_by_domain(self):
        """Should detect watchlist domains."""
        from app.services.compliance_service import is_on_watchlist

        assert is_on_watchlist("Сбербанк", "sberbank.ru") is True
        assert is_on_watchlist("Some Gov", "gov.ru") is True
        assert is_on_watchlist("Regular Company", "regular.ru") is False

    def test_is_on_watchlist_by_keyword(self):
        """Should detect watchlist keywords."""
        from app.services.compliance_service import is_on_watchlist

        assert is_on_watchlist("Министерство труда", None) is True
        assert is_on_watchlist("Администрация города", None) is True
        assert is_on_watchlist("Обычная компания", None) is False


# =============================================================================
# EmailService Tests
# =============================================================================

class TestEmailService:
    """Tests for email service."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_llm_router(self):
        """Create mock LLM router."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db, mock_llm_router):
        """Create email service."""
        from app.services.email_service import EmailService
        return EmailService(mock_db, mock_llm_router)

    @pytest.fixture
    def sample_lead(self):
        """Create sample lead."""
        from app.models.domain import EmployerLead
        return EmployerLead(
            company_name="Test Company",
            domain="test.ru",
            source="hh.ru",
        )

    @pytest.fixture
    def sample_contact(self, sample_lead):
        """Create sample contact."""
        from app.models.domain import EmployerContact
        from app.models.enums import ContactRole
        return EmployerContact(
            lead_id=sample_lead.id,
            full_name="Test Contact",
            role=ContactRole.HR_MANAGER,
            email="test@test.ru",
        )

    @pytest.mark.asyncio
    async def test_create_sequence(self, service, sample_lead, sample_contact):
        """Should create new email sequence."""
        sequence = await service.create_sequence(sample_lead, sample_contact)

        assert sequence.lead_id == sample_lead.id
        assert sequence.contact_id == sample_contact.id
        assert sequence.current_step == 0
        assert sequence.is_active is True

    @pytest.mark.asyncio
    async def test_create_sequence_with_campaign(self, service, sample_lead, sample_contact):
        """Should create sequence with campaign ID."""
        campaign_id = uuid4()
        sequence = await service.create_sequence(
            sample_lead, sample_contact, campaign_id=campaign_id
        )

        assert sequence.campaign_id == campaign_id

    def test_get_next_email_type_first(self, service):
        """Should return first touch for step 0."""
        from app.models.enums import EmailType

        email_type = service._get_next_email_type(0)
        assert email_type == EmailType.FIRST_TOUCH

    def test_get_next_email_type_followups(self, service):
        """Should return correct followup types."""
        from app.models.enums import EmailType

        assert service._get_next_email_type(1) == EmailType.FOLLOWUP_1
        assert service._get_next_email_type(2) == EmailType.FOLLOWUP_2
        assert service._get_next_email_type(3) == EmailType.BREAKUP

    def test_get_next_email_type_none(self, service):
        """Should return None after sequence complete."""
        assert service._get_next_email_type(4) is None
        assert service._get_next_email_type(10) is None

    def test_build_unsubscribe_url(self, service):
        """Should build valid unsubscribe URL."""
        lead_id = uuid4()
        contact_id = uuid4()

        url = service._build_unsubscribe_url(lead_id, contact_id)

        assert "unsubscribe" in url
        assert str(lead_id) in url
        assert str(contact_id) in url

    @pytest.mark.asyncio
    async def test_schedule_followup(self, service, sample_lead, sample_contact):
        """Should schedule next followup."""
        from app.models.domain import EmailMessage, EmailSequence

        sequence = await service.create_sequence(sample_lead, sample_contact)
        sequence.current_step = 1

        email = EmailMessage(
            sequence_id=sequence.id,
            lead_id=sample_lead.id,
            contact_id=sample_contact.id,
            email_type="first_touch",
            subject="Test",
            body="Test body",
            step_number=1,
            sent_at=datetime.now(UTC),
        )

        scheduled = await service.schedule_followup(sequence, email)

        assert scheduled is not None
        assert scheduled > datetime.now(UTC)
        assert sequence.next_email_at == scheduled

    @pytest.mark.asyncio
    async def test_schedule_followup_inactive_sequence(self, service, sample_lead, sample_contact):
        """Should not schedule if sequence inactive."""
        from app.models.domain import EmailMessage, EmailSequence

        sequence = await service.create_sequence(sample_lead, sample_contact)
        sequence.is_active = False

        email = EmailMessage(
            sequence_id=sequence.id,
            lead_id=sample_lead.id,
            contact_id=sample_contact.id,
            email_type="first_touch",
            subject="Test",
            body="Test body",
            step_number=1,
        )

        scheduled = await service.schedule_followup(sequence, email)

        assert scheduled is None

    @pytest.mark.asyncio
    async def test_process_reply(self, service, sample_lead, sample_contact):
        """Should process reply and pause sequence."""
        from app.models.domain import EmailMessage, EmailSequence

        sequence = await service.create_sequence(sample_lead, sample_contact)
        email = EmailMessage(
            sequence_id=sequence.id,
            lead_id=sample_lead.id,
            contact_id=sample_contact.id,
            email_type="first_touch",
            subject="Test",
            body="Test body",
            step_number=1,
        )

        await service.process_reply(email, "Thanks for reaching out!", sequence)

        assert email.replied is True
        assert email.replied_at is not None
        assert email.reply_text == "Thanks for reaching out!"
        assert sequence.is_active is False

    @pytest.mark.asyncio
    async def test_process_bounce(self, service, sample_lead, sample_contact):
        """Should process bounce."""
        from app.models.domain import EmailMessage, EmailSequence

        sequence = await service.create_sequence(sample_lead, sample_contact)
        email = EmailMessage(
            sequence_id=sequence.id,
            lead_id=sample_lead.id,
            contact_id=sample_contact.id,
            email_type="first_touch",
            subject="Test",
            body="Test body",
            step_number=1,
        )

        await service.process_bounce(email, "hard", "mailbox not found")

        assert email.bounced is True
        assert email.bounce_type == "hard"
        assert email.bounce_reason == "mailbox not found"
        assert email.delivered is False

    @pytest.mark.asyncio
    async def test_complete_sequence(self, service, sample_lead, sample_contact):
        """Should complete sequence."""
        sequence = await service.create_sequence(sample_lead, sample_contact)

        await service.complete_sequence(sequence, reason="all_emails_sent")

        assert sequence.is_active is False
        assert sequence.completed_at is not None


# =============================================================================
# LeadService Tests
# =============================================================================

class TestLeadService:
    """Tests for lead service."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        """Create lead service with mocked dependencies."""
        from app.services.lead_service import LeadService

        service = LeadService(mock_session)
        # Mock repositories
        service.lead_repo = AsyncMock()
        service.company_repo = AsyncMock()
        service.contact_repo = AsyncMock()
        service.event_repo = AsyncMock()
        service.event_repo.create = AsyncMock(return_value=MagicMock())
        return service

    @pytest.fixture
    def sample_lead(self):
        """Create sample lead."""
        from app.models.domain import EmployerLead
        return EmployerLead(
            company_name="Test Company",
            domain="test.ru",
            source="hh.ru",
        )

    @pytest.mark.asyncio
    async def test_create_lead_success(self, service, sample_lead):
        """Should create lead successfully."""
        service.lead_repo.get_by_domain = AsyncMock(return_value=None)
        service.lead_repo.create = AsyncMock(return_value=sample_lead)

        result = await service.create_lead(sample_lead)

        assert result == sample_lead
        service.lead_repo.create.assert_called_once_with(sample_lead)
        service.event_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_lead_duplicate(self, service, sample_lead):
        """Should raise error on duplicate."""
        from app.core.exceptions import DuplicateLeadError
        from app.models.domain import EmployerLead

        existing = EmployerLead(
            company_name="Existing Company",
            domain="test.ru",
            source="hh.ru",
        )
        service.lead_repo.get_by_domain = AsyncMock(return_value=existing)

        with pytest.raises(DuplicateLeadError):
            await service.create_lead(sample_lead)

    @pytest.mark.asyncio
    async def test_create_lead_skip_duplicate_check(self, service, sample_lead):
        """Should skip duplicate check when disabled."""
        service.lead_repo.create = AsyncMock(return_value=sample_lead)

        result = await service.create_lead(sample_lead, check_duplicate=False)

        assert result == sample_lead
        service.lead_repo.get_by_domain.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_lead_found(self, service, sample_lead):
        """Should return lead when found."""
        service.lead_repo.get_by_id = AsyncMock(return_value=sample_lead)

        result = await service.get_lead(sample_lead.id)

        assert result == sample_lead

    @pytest.mark.asyncio
    async def test_get_lead_not_found(self, service):
        """Should raise error when not found."""
        from app.core.exceptions import LeadNotFoundError

        service.lead_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(LeadNotFoundError):
            await service.get_lead(uuid4())

    @pytest.mark.asyncio
    async def test_list_leads_with_status(self, service, sample_lead):
        """Should list leads by status."""
        from app.models.enums import LeadStatus

        service.lead_repo.list_by_status = AsyncMock(return_value=[sample_lead])

        result = await service.list_leads(status=LeadStatus.LEAD_FOUND)

        assert len(result) == 1
        service.lead_repo.list_by_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_transition_lead(self, service, sample_lead):
        """Should transition lead status."""
        from app.models.enums import LeadStatus

        sample_lead.status = LeadStatus.LEAD_FOUND
        service.lead_repo.get_by_id = AsyncMock(return_value=sample_lead)
        service.lead_repo.update = AsyncMock(return_value=sample_lead)

        result = await service.transition_lead(
            sample_lead.id,
            LeadStatus.ENRICHED,
            reason="enrichment_complete",
        )

        assert result.status == LeadStatus.ENRICHED
        service.lead_repo.update.assert_called_once()
        service.event_repo.create.assert_called()

    @pytest.mark.asyncio
    async def test_enrich_lead(self, service, sample_lead):
        """Should enrich lead with profile and contacts."""
        from app.models.domain import CompanyProfile, EmployerContact
        from app.models.enums import ContactRole, HiringIntensity, IndustrySegment, LeadStatus

        sample_lead.status = LeadStatus.LEAD_FOUND
        service.lead_repo.get_by_id = AsyncMock(return_value=sample_lead)
        service.lead_repo.update = AsyncMock(return_value=sample_lead)
        service.company_repo.create = AsyncMock()
        service.contact_repo.create_many = AsyncMock()

        profile = CompanyProfile(
            lead_id=sample_lead.id,
            industry=IndustrySegment.RETAIL,
            hiring_intensity=HiringIntensity.HIGH,
        )
        contacts = [
            EmployerContact(
                lead_id=sample_lead.id,
                full_name="Test Contact",
                role=ContactRole.HR_MANAGER,
            )
        ]

        result = await service.enrich_lead(sample_lead.id, profile, contacts)

        assert result.company_profile_id == profile.id
        assert result.status == LeadStatus.ENRICHED
        service.company_repo.create.assert_called_once_with(profile)
        service.contact_repo.create_many.assert_called_once_with(contacts)

    @pytest.mark.asyncio
    async def test_score_lead_high_score(self, service, sample_lead):
        """Should score lead and transition to SCORED."""
        from app.models.domain import LeadScore, LeadSegment
        from app.models.enums import IndustrySegment, LeadPriority, LeadStatus

        sample_lead.status = LeadStatus.ENRICHED
        service.lead_repo.get_by_id = AsyncMock(return_value=sample_lead)
        service.lead_repo.update = AsyncMock(return_value=sample_lead)

        score = LeadScore(
            lead_id=sample_lead.id,
            total_score=75.0,
            hiring_intensity_score=80.0,
            industry_fit_score=70.0,
            contact_quality_score=75.0,
            company_size_score=70.0,
            recency_score=80.0,
        )
        segment = LeadSegment(
            lead_id=sample_lead.id,
            segment=IndustrySegment.RETAIL,
            communication_angle="speed",
            tone="professional",
            offer_type="general",
            priority=LeadPriority.HIGH,
            pain_statement="Test pain",
            value_proposition="Test value",
            proof_point="Test proof",
            suggested_cta="Test CTA",
        )

        result = await service.score_lead(sample_lead.id, score, segment)

        assert result.status == LeadStatus.SCORED

    @pytest.mark.asyncio
    async def test_score_lead_low_score_archives(self, service, sample_lead):
        """Should archive lead with low score."""
        from app.models.domain import LeadScore, LeadSegment
        from app.models.enums import IndustrySegment, LeadPriority, LeadStatus

        sample_lead.status = LeadStatus.ENRICHED
        service.lead_repo.get_by_id = AsyncMock(return_value=sample_lead)
        service.lead_repo.update = AsyncMock(return_value=sample_lead)

        score = LeadScore(
            lead_id=sample_lead.id,
            total_score=15.0,  # Below threshold
            hiring_intensity_score=20.0,
            industry_fit_score=10.0,
            contact_quality_score=15.0,
            company_size_score=10.0,
            recency_score=20.0,
        )
        segment = LeadSegment(
            lead_id=sample_lead.id,
            segment=IndustrySegment.RETAIL,
            communication_angle="speed",
            tone="professional",
            offer_type="general",
            priority=LeadPriority.LOW,
            pain_statement="Test pain",
            value_proposition="Test value",
            proof_point="Test proof",
            suggested_cta="Test CTA",
        )

        result = await service.score_lead(sample_lead.id, score, segment)

        assert result.status == LeadStatus.ARCHIVED

    @pytest.mark.asyncio
    async def test_archive_lead(self, service, sample_lead):
        """Should archive lead with reason."""
        from app.models.enums import LeadStatus

        sample_lead.status = LeadStatus.LEAD_FOUND
        service.lead_repo.get_by_id = AsyncMock(return_value=sample_lead)
        service.lead_repo.update = AsyncMock(return_value=sample_lead)

        result = await service.archive_lead(sample_lead.id, "no_contact")

        assert result.status == LeadStatus.ARCHIVED

    @pytest.mark.asyncio
    async def test_get_lead_with_details(self, service, sample_lead):
        """Should return lead with profile and contacts."""
        from app.models.domain import CompanyProfile, EmployerContact
        from app.models.enums import ContactRole, HiringIntensity, IndustrySegment

        profile = CompanyProfile(
            lead_id=sample_lead.id,
            industry=IndustrySegment.RETAIL,
            hiring_intensity=HiringIntensity.HIGH,
        )
        contacts = [
            EmployerContact(
                lead_id=sample_lead.id,
                full_name="Test Contact",
                role=ContactRole.HR_MANAGER,
            )
        ]

        sample_lead.company_profile_id = profile.id
        service.lead_repo.get_by_id = AsyncMock(return_value=sample_lead)
        service.company_repo.get_by_id = AsyncMock(return_value=profile)
        service.contact_repo.get_by_lead_id = AsyncMock(return_value=contacts)

        result = await service.get_lead_with_details(sample_lead.id)

        assert result["lead"] == sample_lead
        assert result["profile"] == profile
        assert result["contacts"] == contacts
