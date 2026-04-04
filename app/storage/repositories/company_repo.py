"""Company profile repository."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import CompanyProfileDB
from app.models.domain import CompanyProfile
from app.models.enums import HiringIntensity, IndustrySegment


class CompanyRepository:
    """Repository for CompanyProfile operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, profile: CompanyProfile) -> CompanyProfile:
        """Create a new company profile.

        Args:
            profile: Profile to create

        Returns:
            Created profile
        """
        db_profile = CompanyProfileDB(
            id=profile.id,
            lead_id=profile.lead_id,
            legal_name=profile.legal_name,
            brand_name=profile.brand_name,
            inn=profile.inn,
            domain=profile.domain,
            website_url=profile.website_url,
            industry=profile.industry.value,
            sub_industry=profile.sub_industry,
            employee_count=profile.employee_count,
            employee_count_source=profile.employee_count_source,
            city=profile.city,
            region=profile.region,
            branches_count=profile.branches_count,
            cities_presence=profile.cities_presence,
            active_vacancies_count=profile.active_vacancies_count,
            hiring_intensity=profile.hiring_intensity.value,
            vacancy_sources=profile.vacancy_sources,
            typical_roles=profile.typical_roles,
            avg_vacancy_age_days=profile.avg_vacancy_age_days,
            has_hr_department=profile.has_hr_department,
            pain_points=profile.pain_points,
            personalization_hooks=profile.personalization_hooks,
            recent_news=profile.recent_news,
            enriched_at=profile.enriched_at,
            enrichment_source=profile.enrichment_source,
        )

        self.session.add(db_profile)
        await self.session.flush()

        return profile

    async def get_by_id(self, profile_id: UUID) -> CompanyProfile | None:
        """Get profile by ID.

        Args:
            profile_id: Profile UUID

        Returns:
            Profile or None
        """
        result = await self.session.execute(
            select(CompanyProfileDB).where(CompanyProfileDB.id == profile_id)
        )
        db_profile = result.scalar_one_or_none()

        if not db_profile:
            return None

        return self._to_domain(db_profile)

    async def get_by_lead_id(self, lead_id: UUID) -> CompanyProfile | None:
        """Get profile by lead ID.

        Args:
            lead_id: Lead UUID

        Returns:
            Profile or None
        """
        result = await self.session.execute(
            select(CompanyProfileDB).where(CompanyProfileDB.lead_id == lead_id)
        )
        db_profile = result.scalar_one_or_none()

        if not db_profile:
            return None

        return self._to_domain(db_profile)

    async def get_by_inn(self, inn: str) -> CompanyProfile | None:
        """Get profile by INN.

        Args:
            inn: Company INN

        Returns:
            Profile or None
        """
        result = await self.session.execute(
            select(CompanyProfileDB).where(CompanyProfileDB.inn == inn)
        )
        db_profile = result.scalar_one_or_none()

        if not db_profile:
            return None

        return self._to_domain(db_profile)

    async def update(self, profile: CompanyProfile) -> CompanyProfile:
        """Update company profile.

        Args:
            profile: Profile with updated data

        Returns:
            Updated profile
        """
        await self.session.execute(
            update(CompanyProfileDB)
            .where(CompanyProfileDB.id == profile.id)
            .values(
                legal_name=profile.legal_name,
                brand_name=profile.brand_name,
                inn=profile.inn,
                domain=profile.domain,
                website_url=profile.website_url,
                industry=profile.industry.value,
                sub_industry=profile.sub_industry,
                employee_count=profile.employee_count,
                employee_count_source=profile.employee_count_source,
                city=profile.city,
                region=profile.region,
                branches_count=profile.branches_count,
                cities_presence=profile.cities_presence,
                active_vacancies_count=profile.active_vacancies_count,
                hiring_intensity=profile.hiring_intensity.value,
                vacancy_sources=profile.vacancy_sources,
                typical_roles=profile.typical_roles,
                avg_vacancy_age_days=profile.avg_vacancy_age_days,
                has_hr_department=profile.has_hr_department,
                pain_points=profile.pain_points,
                personalization_hooks=profile.personalization_hooks,
                recent_news=profile.recent_news,
                enriched_at=profile.enriched_at,
                enrichment_source=profile.enrichment_source,
            )
        )

        return profile

    def _to_domain(self, db_profile: CompanyProfileDB) -> CompanyProfile:
        """Convert DB model to domain model."""
        return CompanyProfile(
            id=db_profile.id,
            lead_id=db_profile.lead_id,
            legal_name=db_profile.legal_name,
            brand_name=db_profile.brand_name,
            inn=db_profile.inn,
            domain=db_profile.domain,
            website_url=db_profile.website_url,
            industry=IndustrySegment(db_profile.industry),
            sub_industry=db_profile.sub_industry,
            employee_count=db_profile.employee_count,
            employee_count_source=db_profile.employee_count_source,
            city=db_profile.city,
            region=db_profile.region,
            branches_count=db_profile.branches_count,
            cities_presence=db_profile.cities_presence or [],
            active_vacancies_count=db_profile.active_vacancies_count,
            hiring_intensity=HiringIntensity(db_profile.hiring_intensity),
            vacancy_sources=db_profile.vacancy_sources or [],
            typical_roles=db_profile.typical_roles or [],
            avg_vacancy_age_days=db_profile.avg_vacancy_age_days,
            has_hr_department=db_profile.has_hr_department,
            pain_points=db_profile.pain_points or [],
            personalization_hooks=db_profile.personalization_hooks or [],
            recent_news=db_profile.recent_news or [],
            enriched_at=db_profile.enriched_at,
            enrichment_source=db_profile.enrichment_source,
        )
