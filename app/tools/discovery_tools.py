"""Discovery tools - finding employers from various sources.

Интеграция с hh.ru API, Avito, 2GIS согласно ARCHITECTURE.md раздел 9.
"""

from datetime import datetime, timezone

UTC = timezone.utc
from typing import Any
from uuid import uuid4

import httpx

from app.config import settings
from app.models.domain import EmployerLead
from app.models.enums import LeadStatus


async def find_employers_hh(
    query: str | None = None,
    area: int | None = 1,  # 1 = Москва
    industry: str | None = None,
    only_with_vacancies: bool = True,
    per_page: int = 20,
    page: int = 0,
) -> list[dict[str, Any]]:
    """Find employers on hh.ru matching search criteria.

    Args:
        query: Search query (company name, keywords)
        area: Region ID (1=Moscow, 2=SPb, etc.)
        industry: Industry filter
        only_with_vacancies: Only return employers with active vacancies
        per_page: Results per page (max 100)
        page: Page number

    Returns:
        List of employer data dicts
    """
    base_url = "https://api.hh.ru/employers"

    params: dict[str, Any] = {
        "per_page": min(per_page, 100),
        "page": page,
    }

    if query:
        params["text"] = query
    if area:
        params["area"] = area
    if only_with_vacancies:
        params["only_with_vacancies"] = "true"

    headers = {
        "User-Agent": "OtclickEmployerEngine/1.0",
    }

    # Add API token if available
    if settings.hh_api_token:
        headers["Authorization"] = f"Bearer {settings.hh_api_token.get_secret_value()}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(base_url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("items", [])
    except Exception as e:
        # Log error and return empty list
        print(f"Error fetching employers from hh.ru: {e}")
        return []


async def parse_hh_employer(employer_id: str) -> dict[str, Any] | None:
    """Get detailed employer info from hh.ru.

    Args:
        employer_id: hh.ru employer ID

    Returns:
        Employer data dict or None if not found
    """
    url = f"https://api.hh.ru/employers/{employer_id}"

    headers = {
        "User-Agent": "OtclickEmployerEngine/1.0",
    }

    if settings.hh_api_token:
        headers["Authorization"] = f"Bearer {settings.hh_api_token.get_secret_value()}"

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

    headers = {
        "User-Agent": "OtclickEmployerEngine/1.0",
    }

    if settings.hh_api_token:
        headers["Authorization"] = f"Bearer {settings.hh_api_token.get_secret_value()}"

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
        employer_data: Raw data from hh.ru API

    Returns:
        New EmployerLead instance
    """
    # Extract domain from site URL if available
    domain = None
    site_url = employer_data.get("site_url")
    if site_url:
        from urllib.parse import urlparse
        parsed = urlparse(site_url)
        domain = parsed.netloc.replace("www.", "")

    # Extract area/city
    area = employer_data.get("area", {})
    city = area.get("name") if isinstance(area, dict) else None

    return EmployerLead(
        id=uuid4(),
        company_name=employer_data.get("name", "Unknown"),
        domain=domain,
        source="hh.ru",
        source_url=employer_data.get("alternate_url"),
        city=city,
        status=LeadStatus.LEAD_FOUND,
        status_changed_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


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
