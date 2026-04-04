"""Tests for scoring tools."""

import pytest

from app.models.domain import CompanyProfile, EmployerContact, EmployerLead
from app.models.enums import (
    ContactRole,
    HiringIntensity,
    IndustrySegment,
    LeadPriority,
)
from app.tools.scoring_tools import calculate_score, determine_segment


class TestCalculateScore:
    """Tests for calculate_score function."""

    @pytest.fixture
    def lead(self) -> EmployerLead:
        """Create test lead."""
        return EmployerLead(
            company_name="Test Company",
            source="hh.ru",
            city="Москва",
        )

    @pytest.fixture
    def retail_profile(self, lead: EmployerLead) -> CompanyProfile:
        """Create retail company profile."""
        return CompanyProfile(
            lead_id=lead.id,
            industry=IndustrySegment.RETAIL,
            hiring_intensity=HiringIntensity.HIGH,
            active_vacancies_count=15,
            employee_count=200,
        )

    @pytest.fixture
    def hr_contact(self, lead: EmployerLead) -> EmployerContact:
        """Create HR contact."""
        return EmployerContact(
            lead_id=lead.id,
            full_name="HR Manager",
            role=ContactRole.HR_MANAGER,
            email="hr@test.com",
            email_verified=True,
        )

    def test_score_with_all_data(
        self,
        lead: EmployerLead,
        retail_profile: CompanyProfile,
        hr_contact: EmployerContact,
    ) -> None:
        """High score when all data is good."""
        score = calculate_score(lead, retail_profile, [hr_contact])

        assert score.total_score >= 70
        assert score.hiring_intensity_score >= 70
        assert score.industry_fit_score >= 70
        assert score.contact_quality_score >= 70

    def test_score_without_profile(self, lead: EmployerLead) -> None:
        """Low scores without profile data."""
        score = calculate_score(lead, None, [])

        assert score.hiring_intensity_score == 30.0
        assert score.industry_fit_score == 40.0
        assert score.contact_quality_score == 0.0

    def test_score_without_contacts(
        self,
        lead: EmployerLead,
        retail_profile: CompanyProfile,
    ) -> None:
        """Contact score is 0 without contacts."""
        score = calculate_score(lead, retail_profile, [])

        assert score.contact_quality_score == 0.0
        assert score.hiring_intensity_score > 0

    def test_hiring_intensity_scoring(self, lead: EmployerLead) -> None:
        """Different hiring intensities produce different scores."""
        low_profile = CompanyProfile(
            lead_id=lead.id,
            hiring_intensity=HiringIntensity.LOW,
        )
        high_profile = CompanyProfile(
            lead_id=lead.id,
            hiring_intensity=HiringIntensity.AGGRESSIVE,
        )

        low_score = calculate_score(lead, low_profile, [])
        high_score = calculate_score(lead, high_profile, [])

        assert high_score.hiring_intensity_score > low_score.hiring_intensity_score
        assert high_score.hiring_intensity_score == 100.0
        assert low_score.hiring_intensity_score == 20.0

    def test_industry_fit_scoring(self, lead: EmployerLead) -> None:
        """Target industries score higher."""
        retail_profile = CompanyProfile(
            lead_id=lead.id,
            industry=IndustrySegment.RETAIL,
        )
        other_profile = CompanyProfile(
            lead_id=lead.id,
            industry=IndustrySegment.OTHER,
        )

        retail_score = calculate_score(lead, retail_profile, [])
        other_score = calculate_score(lead, other_profile, [])

        assert retail_score.industry_fit_score > other_score.industry_fit_score
        assert retail_score.industry_fit_score == 90.0
        assert other_score.industry_fit_score == 40.0

    def test_contact_quality_scoring(self, lead: EmployerLead) -> None:
        """Verified HR contacts score higher."""
        unverified_contact = EmployerContact(
            lead_id=lead.id,
            full_name="Someone",
            role=ContactRole.OTHER,
        )
        verified_hr = EmployerContact(
            lead_id=lead.id,
            full_name="HR Manager",
            role=ContactRole.HR_MANAGER,
            email="hr@test.com",
            email_verified=True,
            phone="+7123456789",
        )

        unverified_score = calculate_score(lead, None, [unverified_contact])
        verified_score = calculate_score(lead, None, [verified_hr])

        assert verified_score.contact_quality_score > unverified_score.contact_quality_score

    def test_company_size_scoring(self, lead: EmployerLead) -> None:
        """Larger companies score higher."""
        small_profile = CompanyProfile(
            lead_id=lead.id,
            employee_count=10,
        )
        large_profile = CompanyProfile(
            lead_id=lead.id,
            employee_count=500,
        )

        small_score = calculate_score(lead, small_profile, [])
        large_score = calculate_score(lead, large_profile, [])

        assert large_score.company_size_score > small_score.company_size_score

    def test_score_has_reasoning(
        self,
        lead: EmployerLead,
        retail_profile: CompanyProfile,
        hr_contact: EmployerContact,
    ) -> None:
        """Score includes reasoning text."""
        score = calculate_score(lead, retail_profile, [hr_contact])

        assert score.reasoning is not None
        assert len(score.reasoning) > 0


class TestDetermineSegment:
    """Tests for determine_segment function."""

    @pytest.fixture
    def lead(self) -> EmployerLead:
        """Create test lead."""
        return EmployerLead(
            company_name="Test Company",
            source="hh.ru",
        )

    @pytest.fixture
    def high_score(self, lead: EmployerLead):
        """Create high score."""
        from app.models.domain import LeadScore
        return LeadScore(
            lead_id=lead.id,
            total_score=85.0,
            hiring_intensity_score=90.0,
            industry_fit_score=80.0,
            contact_quality_score=85.0,
            company_size_score=80.0,
            recency_score=90.0,
        )

    @pytest.fixture
    def low_score(self, lead: EmployerLead):
        """Create low score."""
        from app.models.domain import LeadScore
        return LeadScore(
            lead_id=lead.id,
            total_score=35.0,
            hiring_intensity_score=30.0,
            industry_fit_score=40.0,
            contact_quality_score=30.0,
            company_size_score=40.0,
            recency_score=30.0,
        )

    def test_segment_from_profile_industry(self, lead: EmployerLead, high_score) -> None:
        """Segment uses profile industry."""
        profile = CompanyProfile(
            lead_id=lead.id,
            industry=IndustrySegment.HORECA,
        )

        segment = determine_segment(lead, profile, high_score)

        assert segment.segment == IndustrySegment.HORECA

    def test_segment_without_profile(self, lead: EmployerLead, high_score) -> None:
        """Segment defaults to OTHER without profile."""
        segment = determine_segment(lead, None, high_score)

        assert segment.segment == IndustrySegment.OTHER

    def test_priority_from_score(self, lead: EmployerLead, high_score, low_score) -> None:
        """Priority is based on score."""
        high_segment = determine_segment(lead, None, high_score)
        low_segment = determine_segment(lead, None, low_score)

        assert high_segment.priority == LeadPriority.HIGH
        assert low_segment.priority == LeadPriority.LOW

    def test_critical_priority_for_90_plus(self, lead: EmployerLead) -> None:
        """Score 90+ gets CRITICAL priority."""
        from app.models.domain import LeadScore
        critical_score = LeadScore(
            lead_id=lead.id,
            total_score=95.0,
            hiring_intensity_score=100.0,
            industry_fit_score=90.0,
            contact_quality_score=90.0,
            company_size_score=90.0,
            recency_score=100.0,
        )

        segment = determine_segment(lead, None, critical_score)

        assert segment.priority == LeadPriority.CRITICAL

    def test_segment_has_communication_strategy(
        self,
        lead: EmployerLead,
        high_score,
    ) -> None:
        """Segment includes communication strategy."""
        profile = CompanyProfile(
            lead_id=lead.id,
            industry=IndustrySegment.RETAIL,
        )

        segment = determine_segment(lead, profile, high_score)

        assert segment.communication_angle is not None
        assert segment.tone is not None
        assert segment.pain_statement is not None
        assert segment.value_proposition is not None
        assert segment.proof_point is not None
        assert segment.suggested_cta is not None

    def test_urgent_offer_for_aggressive_hiring(
        self,
        lead: EmployerLead,
        high_score,
    ) -> None:
        """Aggressive hiring intensity gets urgent offer type."""
        profile = CompanyProfile(
            lead_id=lead.id,
            industry=IndustrySegment.LOGISTICS,
            hiring_intensity=HiringIntensity.AGGRESSIVE,
        )

        segment = determine_segment(lead, profile, high_score)

        assert segment.offer_type == "urgent"

    def test_retail_segment_strategy(self, lead: EmployerLead, high_score) -> None:
        """Retail segment has speed-focused strategy."""
        profile = CompanyProfile(
            lead_id=lead.id,
            industry=IndustrySegment.RETAIL,
        )

        segment = determine_segment(lead, profile, high_score)

        assert segment.communication_angle == "speed"
        assert "кассир" in segment.pain_statement.lower() or "48" in segment.value_proposition

    def test_horeca_segment_strategy(self, lead: EmployerLead, high_score) -> None:
        """HoReCa segment has reliability-focused strategy."""
        profile = CompanyProfile(
            lead_id=lead.id,
            industry=IndustrySegment.HORECA,
        )

        segment = determine_segment(lead, profile, high_score)

        assert segment.communication_angle == "reliability"
