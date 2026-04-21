"""Unit tests for Round 3 services.

Tests for:
1. Account-based outreach
2. Data quality / contact confidence
3. Lead freshness
4. Manager feedback
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# Patch path for redis
REDIS_PATCH = "app.storage.redis.get_redis"

UTC = timezone.utc


class TestAccountBasedOutreach:
    """Tests for account-based outreach service."""

    @pytest.fixture
    def service(self):
        from app.services.account_outreach import AccountOutreachService
        return AccountOutreachService()

    @pytest.mark.asyncio
    async def test_initialize_account(self, service):
        """Should initialize account with contacts."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)

        with patch(REDIS_PATCH, return_value=mock_redis):
            state = await service.initialize_account(
                lead_id="lead-123",
                contact_ids=["c1", "c2", "c3"],
            )

        assert state.lead_id == "lead-123"
        assert state.status.value == "in_progress"
        assert len(state.contacts) == 3
        assert state.total_touches == 0
        assert state.started_at is not None

    @pytest.mark.asyncio
    async def test_get_next_touch_ready(self, service):
        """Should recommend touch when contact is ready."""
        import json
        state_data = {
            "lead_id": "lead-123",
            "status": "in_progress",
            "contacts": [
                {"contact_id": "c1", "status": "pending", "touches": 0, "last_touch_at": None},
            ],
            "total_touches": 0,
            "total_bounces": 0,
            "has_reply": False,
            "has_positive_reply": False,
            "stop_reason": None,
            "stopped_at": None,
            "started_at": datetime.now(UTC).isoformat(),
            "last_touch_at": None,
            "next_touch_at": None,
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(state_data))

        with patch(REDIS_PATCH, return_value=mock_redis):
            recommendation = await service.get_next_touch("lead-123")

        assert recommendation.should_touch is True
        assert recommendation.contact_id == "c1"
        assert recommendation.touch_number == 1
        assert recommendation.reason == "contact_ready"

    @pytest.mark.asyncio
    async def test_get_next_touch_stopped_account(self, service):
        """Should not recommend touch for stopped account."""
        import json
        state_data = {
            "lead_id": "lead-123",
            "status": "stopped",
            "contacts": [],
            "total_touches": 0,
            "total_bounces": 0,
            "has_reply": False,
            "has_positive_reply": False,
            "stop_reason": "manual",
            "stopped_at": datetime.now(UTC).isoformat(),
            "started_at": datetime.now(UTC).isoformat(),
            "last_touch_at": None,
            "next_touch_at": None,
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(state_data))

        with patch(REDIS_PATCH, return_value=mock_redis):
            recommendation = await service.get_next_touch("lead-123")

        assert recommendation.should_touch is False
        assert "stopped" in recommendation.reason

    @pytest.mark.asyncio
    async def test_handle_reply_stops_account(self, service):
        """Reply should stop outreach to account when stop_on_any_reply is enabled."""
        import json
        state_data = {
            "lead_id": "lead-123",
            "status": "in_progress",
            "contacts": [
                {"contact_id": "c1", "status": "active", "touches": 1, "last_touch_at": datetime.now(UTC).isoformat()},
            ],
            "total_touches": 1,
            "total_bounces": 0,
            "has_reply": False,
            "has_positive_reply": False,
            "stop_reason": None,
            "stopped_at": None,
            "started_at": datetime.now(UTC).isoformat(),
            "last_touch_at": datetime.now(UTC).isoformat(),
            "next_touch_at": None,
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(state_data))
        mock_redis.set = AsyncMock(return_value=True)

        with patch(REDIS_PATCH, return_value=mock_redis):
            state = await service.handle_reply(
                lead_id="lead-123",
                contact_id="c1",
                is_positive=True,
            )

        assert state.has_reply is True
        assert state.has_positive_reply is True
        assert state.status.value == "qualified"
        assert state.stop_reason.value == "positive_reply"

    @pytest.mark.asyncio
    async def test_handle_bounce_stops_at_threshold(self, service):
        """Account should stop when bounce threshold is reached."""
        import json
        state_data = {
            "lead_id": "lead-123",
            "status": "in_progress",
            "contacts": [
                {"contact_id": "c1", "status": "active", "touches": 1, "bounces": 0},
            ],
            "total_touches": 1,
            "total_bounces": 1,  # Already has 1 bounce
            "has_reply": False,
            "has_positive_reply": False,
            "stop_reason": None,
            "stopped_at": None,
            "started_at": datetime.now(UTC).isoformat(),
            "last_touch_at": datetime.now(UTC).isoformat(),
            "next_touch_at": None,
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(state_data))
        mock_redis.set = AsyncMock(return_value=True)

        with patch(REDIS_PATCH, return_value=mock_redis):
            state = await service.handle_bounce(
                lead_id="lead-123",
                contact_id="c1",
                is_hard_bounce=True,
            )

        assert state.total_bounces == 2
        assert state.status.value == "stopped"
        assert state.stop_reason.value == "bounce_limit"


class TestContactConfidence:
    """Tests for contact confidence scoring."""

    @pytest.fixture
    def service(self):
        from app.services.data_quality import DataQualityService
        return DataQualityService()

    def test_high_confidence_verified_email(self, service):
        """Verified corporate email should have high confidence."""
        confidence = service.calculate_contact_confidence(
            email="ivan@company.ru",
            email_verified=True,
            full_name="Иван Петров",
            job_title="HR Директор",
            role="HR_MANAGER",
            contact_source="hh.ru",
        )

        assert confidence.overall_score > 0.8
        assert confidence.email_confidence > 0.8
        assert confidence.verification_status == "verified"
        assert len(confidence.issues) == 0

    def test_low_confidence_generic_email(self, service):
        """Generic info@ email should have lower confidence."""
        confidence = service.calculate_contact_confidence(
            email="info@company.ru",
            email_verified=False,
        )

        assert confidence.overall_score < 0.5
        assert confidence.email_confidence < 0.5
        assert "low_email_confidence" in confidence.issues

    def test_bounced_email_low_confidence(self, service):
        """Bounced email should have very low confidence."""
        confidence = service.calculate_contact_confidence(
            email="bounced@company.ru",
            bounce_count=2,
        )

        assert confidence.email_confidence < 0.3
        assert confidence.verification_status == "bounced"

    def test_reply_received_full_confidence(self, service):
        """Email that received a reply should be fully verified."""
        confidence = service.calculate_contact_confidence(
            email="responded@company.ru",
            reply_received=True,
        )

        assert confidence.email_confidence == 1.0
        assert confidence.verification_status == "verified"

    def test_phone_validation_russian(self, service):
        """Russian phone numbers should be validated."""
        confidence = service.calculate_contact_confidence(
            email=None,
            phone="+79261234567",
        )
        assert confidence.phone_confidence >= 0.9

        confidence_bad = service.calculate_contact_confidence(
            email=None,
            phone="123",  # Too short
        )
        assert confidence_bad.phone_confidence < 0.5

    def test_source_quality_affects_score(self, service):
        """Different sources should have different quality scores."""
        confidence_hh = service.calculate_contact_confidence(
            email="test@company.ru",
            contact_source="hh.ru",
        )

        confidence_csv = service.calculate_contact_confidence(
            email="test@company.ru",
            contact_source="csv_import",
        )

        assert confidence_hh.source_quality > confidence_csv.source_quality


class TestSourceQuality:
    """Tests for source quality tracking."""

    @pytest.fixture
    def service(self):
        from app.services.data_quality import DataQualityService
        return DataQualityService()

    @pytest.mark.asyncio
    async def test_record_source_outcome(self, service):
        """Should record outcome for source quality tracking."""
        mock_redis = AsyncMock()
        mock_pipe = MagicMock()
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch(REDIS_PATCH, return_value=mock_redis):
            await service.record_source_outcome(
                source="hh.ru",
                outcome="delivered",
            )

        assert mock_pipe.incr.called

    @pytest.mark.asyncio
    async def test_get_source_quality_with_baseline(self, service):
        """Should return baseline quality for known source."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch(REDIS_PATCH, return_value=mock_redis):
            quality = await service.get_source_quality("hh.ru")

        assert quality.source == "hh.ru"
        assert quality.base_score == 0.85
        assert quality.adjusted_score == 0.85  # No data yet


class TestLeadFreshness:
    """Tests for lead freshness service."""

    @pytest.fixture
    def service(self):
        from app.services.lead_freshness import LeadFreshnessService
        return LeadFreshnessService()

    def test_fresh_lead(self, service):
        """Recently created lead should be fresh."""
        assessment = service.assess_lead_freshness(
            created_at=datetime.now(UTC) - timedelta(days=3),
        )

        assert assessment.status.value == "fresh"
        assert assessment.days_old <= 7
        assert assessment.confidence_adjustment == 0.0

    def test_aging_lead(self, service):
        """Lead older than 7 days should be aging."""
        assessment = service.assess_lead_freshness(
            created_at=datetime.now(UTC) - timedelta(days=15),
        )

        assert assessment.status.value == "aging"
        assert assessment.confidence_adjustment < 0

    def test_stale_lead(self, service):
        """Lead older than stale threshold should be stale."""
        assessment = service.assess_lead_freshness(
            created_at=datetime.now(UTC) - timedelta(days=45),
        )

        assert assessment.status.value == "stale"
        assert assessment.needs_enrichment is True

    def test_expired_lead(self, service):
        """Very old lead should be expired."""
        assessment = service.assess_lead_freshness(
            created_at=datetime.now(UTC) - timedelta(days=100),
        )

        assert assessment.status.value == "expired"
        assert assessment.confidence_adjustment <= -0.20

    def test_never_enriched_needs_enrichment(self, service):
        """Lead never enriched should need high priority enrichment."""
        assessment = service.assess_lead_freshness(
            created_at=datetime.now(UTC) - timedelta(days=5),
            enriched_at=None,
        )

        assert assessment.needs_enrichment is True
        assert assessment.enrichment_priority == "high"
        assert "company_profile" in assessment.stale_fields

    @pytest.mark.asyncio
    async def test_queue_for_enrichment(self, service):
        """Should queue entity for enrichment."""
        mock_redis = AsyncMock()
        mock_redis.zadd = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock(return_value=True)

        with patch(REDIS_PATCH, return_value=mock_redis):
            success = await service.queue_for_enrichment(
                entity_type="lead",
                entity_id="lead-123",
                priority="high",
                reason="stale_data",
            )

        assert success is True
        assert mock_redis.zadd.called


class TestManagerFeedback:
    """Tests for manager feedback service."""

    @pytest.fixture
    def service(self):
        from app.services.manager_feedback import ManagerFeedbackService
        return ManagerFeedbackService()

    @pytest.mark.asyncio
    async def test_submit_positive_feedback(self, service):
        """Positive feedback should increase score."""
        from app.services.manager_feedback import FeedbackType

        mock_redis = AsyncMock()
        mock_redis.lpush = AsyncMock(return_value=1)
        mock_redis.ltrim = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_pipe = MagicMock()
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.incrbyfloat = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch(REDIS_PATCH, return_value=mock_redis):
            feedback = await service.submit_feedback(
                lead_id="lead-123",
                manager_id="manager-1",
                feedback_type=FeedbackType.DEAL_CLOSED,
                comment="Great lead!",
            )

        assert feedback.lead_id == "lead-123"
        assert feedback.feedback_type == FeedbackType.DEAL_CLOSED
        assert feedback.score_adjustment > 0
        assert feedback.sentiment.value == "positive"

    @pytest.mark.asyncio
    async def test_submit_negative_feedback(self, service):
        """Negative feedback should decrease score."""
        from app.services.manager_feedback import FeedbackType

        mock_redis = AsyncMock()
        mock_redis.lpush = AsyncMock(return_value=1)
        mock_redis.ltrim = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_pipe = MagicMock()
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.incrbyfloat = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch(REDIS_PATCH, return_value=mock_redis):
            feedback = await service.submit_feedback(
                lead_id="lead-456",
                manager_id="manager-1",
                feedback_type=FeedbackType.WRONG_CONTACT,
            )

        assert feedback.score_adjustment < 0
        assert feedback.sentiment.value == "negative"

    @pytest.mark.asyncio
    async def test_get_lead_score_adjustment(self, service):
        """Should calculate weighted score adjustment."""
        import json
        from app.services.manager_feedback import FeedbackType, FeedbackSentiment

        feedback_data = [
            {
                "id": "f1",
                "lead_id": "lead-123",
                "manager_id": "m1",
                "feedback_type": "deal_closed",
                "sentiment": "positive",
                "comment": None,
                "score_adjustment": 0.15,
                "created_at": datetime.now(UTC).isoformat(),
            },
            {
                "id": "f2",
                "lead_id": "lead-123",
                "manager_id": "m2",
                "feedback_type": "high_quality_lead",
                "sentiment": "positive",
                "comment": None,
                "score_adjustment": 0.08,
                "created_at": (datetime.now(UTC) - timedelta(days=5)).isoformat(),
            },
        ]

        mock_redis = AsyncMock()
        mock_redis.lrange = AsyncMock(return_value=[json.dumps(f) for f in feedback_data])

        with patch(REDIS_PATCH, return_value=mock_redis):
            adjustment = await service.get_lead_score_adjustment("lead-123")

        # Should be positive due to positive feedback
        assert adjustment > 0
        # Should be clamped to max
        assert adjustment <= service.max_adjustment

    @pytest.mark.asyncio
    async def test_get_source_adjustment(self, service):
        """Should calculate source adjustment from feedback."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=lambda k: {
            "feedback:source:hh.ru:total": "50",
            "feedback:source:hh.ru:positive": "40",
            "feedback:source:hh.ru:negative": "8",
            "feedback:source:hh.ru:adjustment_sum": "2.5",
        }.get(k, "0"))

        with patch(REDIS_PATCH, return_value=mock_redis):
            adjustment = await service.get_source_adjustment("hh.ru")

        assert adjustment.entity_type == "source"
        assert adjustment.entity_value == "hh.ru"
        assert adjustment.sample_size == 50
        assert adjustment.confidence > 0  # Has enough samples


class TestContactPrioritization:
    """Tests for contact prioritization."""

    @pytest.fixture
    def service(self):
        from app.services.data_quality import DataQualityService
        return DataQualityService()

    def test_prioritize_contacts_by_confidence(self, service):
        """Should sort contacts by confidence score."""
        contacts = [
            {
                "email": "info@company.ru",  # Generic email
                "full_name": None,
            },
            {
                "email": "ivan@company.ru",  # Good email
                "email_verified": True,
                "full_name": "Иван Петров",
                "job_title": "HR Manager",
            },
            {
                "email": "bounced@company.ru",
                "bounce_count": 2,
            },
        ]

        prioritized = service.prioritize_contacts(contacts)

        # Best contact should be first
        assert prioritized[0]["email"] == "ivan@company.ru"
        assert prioritized[0]["confidence_score"] > prioritized[1]["confidence_score"]
        # Bounced should be last
        assert prioritized[-1]["email"] == "bounced@company.ru"


class TestFreshnessScore:
    """Tests for freshness score calculation."""

    @pytest.fixture
    def service(self):
        from app.services.lead_freshness import LeadFreshnessService
        return LeadFreshnessService()

    def test_calculate_freshness_score_all_fresh(self, service):
        """All fresh assessments should give high score."""
        from app.services.lead_freshness import FreshnessAssessment, FreshnessStatus

        assessments = [
            FreshnessAssessment(
                entity_type="lead",
                entity_id="1",
                status=FreshnessStatus.FRESH,
                days_old=3,
                last_updated=datetime.now(UTC),
                last_enriched=datetime.now(UTC),
                needs_enrichment=False,
                enrichment_priority="low",
                stale_fields=[],
                confidence_adjustment=0.0,
            ),
            FreshnessAssessment(
                entity_type="contact",
                entity_id="2",
                status=FreshnessStatus.FRESH,
                days_old=5,
                last_updated=datetime.now(UTC),
                last_enriched=datetime.now(UTC),
                needs_enrichment=False,
                enrichment_priority="low",
                stale_fields=[],
                confidence_adjustment=0.0,
            ),
        ]

        score = service.calculate_freshness_score(assessments)

        assert score == 100.0

    def test_calculate_freshness_score_mixed(self, service):
        """Mixed assessments should give medium score."""
        from app.services.lead_freshness import FreshnessAssessment, FreshnessStatus

        assessments = [
            FreshnessAssessment(
                entity_type="lead",
                entity_id="1",
                status=FreshnessStatus.FRESH,
                days_old=3,
                last_updated=datetime.now(UTC),
                last_enriched=None,
                needs_enrichment=True,
                enrichment_priority="high",
                stale_fields=["company_profile"],
                confidence_adjustment=0.0,
            ),
            FreshnessAssessment(
                entity_type="contact",
                entity_id="2",
                status=FreshnessStatus.STALE,
                days_old=90,
                last_updated=datetime.now(UTC),
                last_enriched=None,
                needs_enrichment=True,
                enrichment_priority="high",
                stale_fields=["email_verification"],
                confidence_adjustment=-0.15,
            ),
        ]

        score = service.calculate_freshness_score(assessments)

        # Should be between fresh (100) and stale (40)
        assert 40 < score < 100
