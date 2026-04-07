"""Discovery tools - finding employers from various sources.

Интеграция с hh.ru API, Avito, 2GIS согласно ARCHITECTURE.md раздел 9.
"""

from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from app.config import settings
from app.models.domain import EmployerLead
from app.models.enums import LeadStatus


def _get_hh_headers() -> dict[str, str]:
    """Get headers for HH.ru API requests."""
    headers = {
        "User-Agent": "OtclickEmployerEngine/1.0",
    }
    if settings.hh_api_token:
        headers["Authorization"] = f"Bearer {settings.hh_api_token.get_secret_value()}"
    return headers


async def find_employers_hh(
    query: str | None = None,
    area: int | None = 1,  # 1 = Москва
    industry: str | None = None,
    only_with_vacancies: bool = True,
    per_page: int = 20,
    page: int = 0,
) -> list[dict[str, Any]]:
    """Find employers via HH.ru vacancies search.

    Searches /vacancies and extracts unique employers from results.
    This returns more results than searching /employers directly.

    Args:
        query: Search query (job title, keywords, industry)
        area: Region ID (1=Moscow, 2=SPb, etc.)
        industry: Industry filter (used as search text)
        only_with_vacancies: Ignored (always true for vacancy search)
        per_page: Results per page (max 100)
        page: Page number

    Returns:
        List of unique employer data dicts
    """
    base_url = "https://api.hh.ru/vacancies"

    # Build search text from query and industry
    search_text = query or industry or ""

    params: dict[str, Any] = {
        "per_page": min(per_page * 3, 100),  # Fetch more to get unique employers
        "page": page,
    }

    if search_text:
        params["text"] = search_text
    if area:
        params["area"] = area

    headers = _get_hh_headers()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(base_url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            vacancies = data.get("items", [])

            # Extract unique employers from vacancies
            seen_employers: dict[str, dict[str, Any]] = {}
            for vacancy in vacancies:
                employer = vacancy.get("employer", {})
                employer_id = str(employer.get("id", ""))
                if employer_id and employer_id not in seen_employers:
                    # Store employer with vacancy info for context
                    seen_employers[employer_id] = {
                        "id": employer_id,
                        "name": employer.get("name", "Unknown"),
                        "url": employer.get("url"),
                        "alternate_url": employer.get("alternate_url"),
                        "logo_urls": employer.get("logo_urls"),
                        "vacancies_url": employer.get("vacancies_url"),
                        # Add vacancy context
                        "sample_vacancy": vacancy.get("name"),
                        "area": vacancy.get("area", {}),
                    }

                    # Stop when we have enough unique employers
                    if len(seen_employers) >= per_page:
                        break

            return list(seen_employers.values())

    except Exception as e:
        print(f"Error fetching vacancies from hh.ru: {e}")
        return []


async def parse_hh_employer(employer_id: str) -> dict[str, Any] | None:
    """Get detailed employer info from hh.ru.

    Args:
        employer_id: hh.ru employer ID

    Returns:
        Employer data dict or None if not found
    """
    url = f"https://api.hh.ru/employers/{employer_id}"
    headers = _get_hh_headers()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None
        raise
    except Exception as e:
        print(f"Error fetching employer {employer_id}: {e}")
        return None


async def enrich_employer_domain(employer_id: str) -> str | None:
    """Get domain from employer details.

    Args:
        employer_id: hh.ru employer ID

    Returns:
        Domain string or None
    """
    employer_data = await parse_hh_employer(employer_id)
    if not employer_data:
        return None

    site_url = employer_data.get("site_url")
    if site_url:
        parsed = urlparse(site_url)
        domain = parsed.netloc.replace("www.", "")
        if domain:
            return domain

    return None


async def get_employer_vacancies(
    employer_id: str,
    per_page: int = 20,
) -> list[dict[str, Any]]:
    """Get active vacancies for an employer.

    Args:
        employer_id: hh.ru employer ID
        per_page: Number of vacancies to fetch

    Returns:
        List of vacancy data dicts
    """
    url = "https://api.hh.ru/vacancies"
    params = {
        "employer_id": employer_id,
        "per_page": per_page,
        "order_by": "publication_time",
    }
    headers = _get_hh_headers()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("items", [])
    except Exception as e:
        print(f"Error fetching vacancies for {employer_id}: {e}")
        return []


def create_lead_from_hh(employer_data: dict[str, Any]) -> EmployerLead:
    """Create EmployerLead from hh.ru employer data.

    Args:
        employer_data: Raw data from hh.ru API (either from employers or vacancies)

    Returns:
        New EmployerLead instance
    """
    # Extract domain from site URL if available
    domain = None
    site_url = employer_data.get("site_url")
    if site_url:
        parsed = urlparse(site_url)
        domain = parsed.netloc.replace("www.", "")

    # Extract area/city - handle both formats
    area = employer_data.get("area", {})
    city = area.get("name") if isinstance(area, dict) else None

    # Get employer ID for later enrichment
    employer_id = employer_data.get("id")

    return EmployerLead(
        id=uuid4(),
        company_name=employer_data.get("name", "Unknown"),
        domain=domain,
        source="hh.ru",
        source_url=employer_data.get("alternate_url"),
        city=city,
        status=LeadStatus.LEAD_FOUND,
        status_changed_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


async def create_lead_with_contact(employer_data: dict[str, Any]) -> tuple[EmployerLead, str | None]:
    """Create EmployerLead and find contact email.

    Fetches employer details to get domain and generates hr@domain.

    Args:
        employer_data: Raw data from hh.ru API

    Returns:
        Tuple of (EmployerLead, email or None)
    """
    lead = create_lead_from_hh(employer_data)

    # Try to enrich with domain if not already present
    employer_id = employer_data.get("id")
    email = None

    if not lead.domain and employer_id:
        domain = await enrich_employer_domain(str(employer_id))
        if domain:
            lead.domain = domain

    # Generate hr@domain email
    if lead.domain:
        email = f"hr@{lead.domain}"

    return lead, email


async def search_2gis(
    query: str,
    city: str = "Москва",
    rubric: str | None = None,
) -> list[dict[str, Any]]:
    """Search companies in 2GIS.

    Note: 2GIS API requires registration and API key.
    This is a placeholder implementation.

    Args:
        query: Search query
        city: City name
        rubric: Business category

    Returns:
        List of company data dicts
    """
    # TODO: Implement 2GIS API integration
    # Requires 2GIS API key registration
    return []
