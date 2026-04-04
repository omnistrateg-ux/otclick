"""Pytest fixtures for tests."""

import pytest
from uuid import uuid4

from app.models.domain import (
    CompanyProfile,
    EmployerContact,
    EmployerLead,
    LeadScore,
    LeadSegment,
)
from app.models.enums import (
    ContactRole,
    HiringIntensity,
    IndustrySegment,
    LeadPriority,
    LeadStatus,
)


@pytest.fixture
def sample_lead() -> EmployerLead:
    """Create a sample employer lead for testing."""
    return EmployerLead(
        company_name="ООО Тестовая Компания",
        domain="test-company.ru",
        source="hh.ru",
        source_url="https://hh.ru/employer/12345",
        city="Москва",
        region="Московская область",
    )


@pytest.fixture
def sample_lead_enriched(sample_lead: EmployerLead) -> EmployerLead:
    """Create an enriched lead."""
    sample_lead.status = LeadStatus.ENRICHED
    return sample_lead


@pytest.fixture
def sample_company_profile(sample_lead: EmployerLead) -> CompanyProfile:
    """Create a sample company profile."""
    return CompanyProfile(
        lead_id=sample_lead.id,
        legal_name="ООО Тестовая Компания",
        brand_name="ТестКо",
        inn="7701234567",
        domain="test-company.ru",
        website_url="https://test-company.ru",
        industry=IndustrySegment.RETAIL,
        sub_industry="продуктовый ритейл",
        employee_count=150,
        employee_count_source="hh_estimate",
        city="Москва",
        active_vacancies_count=15,
        hiring_intensity=HiringIntensity.HIGH,
        vacancy_sources=["hh.ru", "avito"],
        typical_roles=["кассир", "продавец", "мерчандайзер"],
        pain_points=["высокая текучка", "сезонные пики"],
        personalization_hooks=["открыли 3 новые точки"],
    )


@pytest.fixture
def sample_contact(sample_lead: EmployerLead) -> EmployerContact:
    """Create a sample employer contact."""
    return EmployerContact(
        lead_id=sample_lead.id,
        full_name="Иванова Мария Петровна",
        first_name="Мария",
        last_name="Иванова",
        role=ContactRole.HR_MANAGER,
        job_title="HR-менеджер",
        email="hr@test-company.ru",
        email_verified=True,
        is_primary=True,
        contact_source="hh_vacancy",
    )


@pytest.fixture
def sample_score(sample_lead: EmployerLead) -> LeadScore:
    """Create a sample lead score."""
    return LeadScore(
        lead_id=sample_lead.id,
        total_score=75.0,
        hiring_intensity_score=90.0,
        industry_fit_score=80.0,
        contact_quality_score=70.0,
        company_size_score=65.0,
        recency_score=60.0,
        reasoning="High hiring intensity in target industry with verified contact",
    )


@pytest.fixture
def sample_segment(sample_lead: EmployerLead) -> LeadSegment:
    """Create a sample lead segment."""
    return LeadSegment(
        lead_id=sample_lead.id,
        segment=IndustrySegment.RETAIL,
        sub_segment="федеральная сеть",
        communication_angle="speed",
        tone="professional",
        offer_type="general",
        priority=LeadPriority.HIGH,
        pain_statement="Сезонные пики, текучка кассиров 80%+",
        value_proposition="Закрываем кассиров за 48 часов",
        proof_point="Работаем с сетями от 50 точек",
        suggested_cta="Имеет смысл обсудить?",
    )
