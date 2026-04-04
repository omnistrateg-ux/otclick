"""Enrichment tools - company profile and contact discovery.

Обогащение данных о компании согласно ARCHITECTURE.md раздел 9.
"""

from datetime import datetime, timezone

UTC = timezone.utc
from typing import Any
from uuid import UUID, uuid4

import httpx

from app.config import settings
from app.models.domain import CompanyProfile, EmployerContact, EmployerLead
from app.models.enums import ContactRole, HiringIntensity, IndustrySegment
from app.tools.discovery_tools import get_employer_vacancies, parse_hh_employer


async def enrich_company(lead: EmployerLead) -> CompanyProfile | None:
    """Enrich lead with company profile data.

    Fetches additional data from hh.ru, website, and other sources.

    Args:
        lead: Lead to enrich

    Returns:
        CompanyProfile or None if enrichment failed
    """
    profile = CompanyProfile(
        id=uuid4(),
        lead_id=lead.id,
        city=lead.city,
    )

    # Try to get data from hh.ru if source_url contains employer ID
    if lead.source == "hh.ru" and lead.source_url:
        employer_id = _extract_hh_employer_id(lead.source_url)
        if employer_id:
            await _enrich_from_hh(profile, employer_id)

    # Determine hiring intensity based on vacancy count
    profile.hiring_intensity = _calculate_hiring_intensity(
        profile.active_vacancies_count or 0
    )

    profile.enriched_at = datetime.now(UTC)
    profile.enrichment_source = lead.source

    return profile


def _extract_hh_employer_id(url: str) -> str | None:
    """Extract employer ID from hh.ru URL.

    Args:
        url: hh.ru employer URL

    Returns:
        Employer ID or None
    """
    # URL format: https://hh.ru/employer/12345
    if "/employer/" in url:
        parts = url.split("/employer/")
        if len(parts) > 1:
            employer_id = parts[1].split("?")[0].split("/")[0]
            if employer_id.isdigit():
                return employer_id
    return None


async def _enrich_from_hh(profile: CompanyProfile, employer_id: str) -> None:
    """Enrich profile with data from hh.ru.

    Args:
        profile: Profile to enrich
        employer_id: hh.ru employer ID
    """
    # Get employer details
    employer_data = await parse_hh_employer(employer_id)
    if employer_data:
        profile.legal_name = employer_data.get("name")
        profile.brand_name = employer_data.get("name")

        # Website
        site_url = employer_data.get("site_url")
        if site_url:
            profile.website_url = site_url
            from urllib.parse import urlparse
            parsed = urlparse(site_url)
            profile.domain = parsed.netloc.replace("www.", "")

        # Area
        area = employer_data.get("area", {})
        if isinstance(area, dict):
            profile.city = area.get("name")

        # Industries
        industries = employer_data.get("industries", [])
        if industries:
            profile.industry = _map_hh_industry(industries[0].get("name", ""))
            profile.sub_industry = industries[0].get("name")

        # Vacancies count
        profile.active_vacancies_count = employer_data.get("open_vacancies", 0)

        # Add vacancy source
        profile.vacancy_sources = ["hh.ru"]

    # Get sample vacancies to extract typical roles
    vacancies = await get_employer_vacancies(employer_id, per_page=10)
    if vacancies:
        roles = set()
        for vacancy in vacancies:
            name = vacancy.get("name", "").lower()
            # Extract common mass-hiring roles
            for role in ["кассир", "продавец", "курьер", "водитель", "грузчик",
                         "официант", "повар", "оператор", "комплектовщик",
                         "уборщик", "охранник", "мерчандайзер"]:
                if role in name:
                    roles.add(role)
        profile.typical_roles = list(roles)


def _map_hh_industry(industry_name: str) -> IndustrySegment:
    """Map hh.ru industry name to IndustrySegment.

    Args:
        industry_name: Industry name from hh.ru

    Returns:
        Mapped IndustrySegment
    """
    industry_lower = industry_name.lower()

    mapping = {
        "розничн": IndustrySegment.RETAIL,
        "торгов": IndustrySegment.TRADE,
        "ресторан": IndustrySegment.HORECA,
        "кафе": IndustrySegment.HORECA,
        "общепит": IndustrySegment.HORECA,
        "логист": IndustrySegment.LOGISTICS,
        "доставк": IndustrySegment.LOGISTICS,
        "транспорт": IndustrySegment.LOGISTICS,
        "строит": IndustrySegment.CONSTRUCTION,
        "производ": IndustrySegment.MANUFACTURING,
        "склад": IndustrySegment.WAREHOUSE,
    }

    for keyword, segment in mapping.items():
        if keyword in industry_lower:
            return segment

    return IndustrySegment.OTHER


def _calculate_hiring_intensity(vacancy_count: int) -> HiringIntensity:
    """Calculate hiring intensity from vacancy count.

    Args:
        vacancy_count: Number of active vacancies

    Returns:
        HiringIntensity level
    """
    if vacancy_count >= 30:
        return HiringIntensity.AGGRESSIVE
    elif vacancy_count >= 10:
        return HiringIntensity.HIGH
    elif vacancy_count >= 3:
        return HiringIntensity.MEDIUM
    else:
        return HiringIntensity.LOW


async def find_contacts(
    lead: EmployerLead,
    profile: CompanyProfile | None = None,
) -> list[EmployerContact]:
    """Find contacts for a lead.

    Searches hh.ru vacancies, website, and other sources.

    Args:
        lead: Lead to find contacts for
        profile: Company profile (optional)

    Returns:
        List of found contacts
    """
    contacts: list[EmployerContact] = []

    # Try hh.ru vacancies
    if lead.source == "hh.ru" and lead.source_url:
        employer_id = _extract_hh_employer_id(lead.source_url)
        if employer_id:
            hh_contacts = await _find_contacts_from_hh_vacancies(lead.id, employer_id)
            contacts.extend(hh_contacts)

    # Try website parsing if domain available
    domain = profile.domain if profile else lead.domain
    if domain and not contacts:
        website_contacts = await _find_contacts_from_website(lead.id, domain)
        contacts.extend(website_contacts)

    # Mark first contact as primary if any found
    if contacts:
        # Prefer HR roles
        hr_contacts = [c for c in contacts if c.role in [
            ContactRole.HR_DIRECTOR, ContactRole.HR_MANAGER, ContactRole.RECRUITER
        ]]
        if hr_contacts:
            hr_contacts[0].is_primary = True
        else:
            contacts[0].is_primary = True

    return contacts


async def _find_contacts_from_hh_vacancies(
    lead_id: UUID,
    employer_id: str,
) -> list[EmployerContact]:
    """Extract contacts from hh.ru vacancy pages.

    Args:
        lead_id: Lead ID for contact association
        employer_id: hh.ru employer ID

    Returns:
        List of contacts found in vacancies
    """
    contacts: list[EmployerContact] = []
    seen_emails: set[str] = set()

    vacancies = await get_employer_vacancies(employer_id, per_page=5)

    for vacancy in vacancies:
        # Check for contact info in vacancy
        vacancy_contacts = vacancy.get("contacts")
        if not vacancy_contacts:
            continue

        name = vacancy_contacts.get("name")
        email = vacancy_contacts.get("email")

        if email and email not in seen_emails:
            seen_emails.add(email)

            # Parse name
            first_name = None
            last_name = None
            if name:
                parts = name.split()
                if len(parts) >= 2:
                    last_name = parts[0]
                    first_name = parts[1]

            contact = EmployerContact(
                id=uuid4(),
                lead_id=lead_id,
                full_name=name or email.split("@")[0],
                first_name=first_name,
                last_name=last_name,
                email=email,
                role=_guess_role_from_title(vacancy_contacts.get("name", "")),
                contact_source="hh_vacancy",
            )

            # Add phone if available
            phones = vacancy_contacts.get("phones", [])
            if phones:
                phone = phones[0].get("formatted")
                if phone:
                    contact.phone = phone

            contacts.append(contact)

    return contacts


async def _find_contacts_from_website(
    lead_id: UUID,
    domain: str,
) -> list[EmployerContact]:
    """Find contacts by parsing company website.

    Args:
        lead_id: Lead ID for contact association
        domain: Company domain

    Returns:
        List of contacts found on website
    """
    # TODO: Implement website parsing for contacts
    # This would involve:
    # 1. Fetching /contacts, /about, /team pages
    # 2. Parsing HTML for email patterns
    # 3. Using email validation
    return []


def _guess_role_from_title(title: str) -> ContactRole:
    """Guess contact role from job title.

    Args:
        title: Job title or name

    Returns:
        Guessed ContactRole
    """
    title_lower = title.lower()

    if "директор" in title_lower and "hr" in title_lower:
        return ContactRole.HR_DIRECTOR
    elif "директор" in title_lower:
        return ContactRole.GENERAL_MANAGER
    elif "менеджер" in title_lower and "hr" in title_lower:
        return ContactRole.HR_MANAGER
    elif "рекрутер" in title_lower or "recruiter" in title_lower:
        return ContactRole.RECRUITER
    elif "hr" in title_lower:
        return ContactRole.HR_MANAGER
    elif "кадр" in title_lower:
        return ContactRole.HR_MANAGER
    elif "владелец" in title_lower or "собственник" in title_lower:
        return ContactRole.OWNER
    else:
        return ContactRole.OTHER
