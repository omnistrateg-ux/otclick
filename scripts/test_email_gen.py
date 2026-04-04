#!/usr/bin/env python3
"""CLI script for testing email generation.

Тестирование генерации писем через EmailIntelligenceEngine.

Usage:
    python scripts/test_email_gen.py --company "Пятёрочка" --segment retail --city "Москва"
    python scripts/test_email_gen.py --company "Шоколадница" --segment horeca --type followup_1
    python scripts/test_email_gen.py --full-sequence --company "X5 Retail" --segment retail
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.email.engine import EmailIntelligenceEngine
from app.email.quality_gate import QualityGate
from app.llm.router import LLMRouter
from app.models.domain import (
    CompanyProfile,
    EmployerContact,
    EmployerLead,
    LeadSegment,
)
from app.models.enums import EmailType, IndustrySegment, LeadPriority, LeadStatus


def create_test_lead(
    company_name: str,
    city: str | None = None,
) -> EmployerLead:
    """Create test lead."""
    return EmployerLead(
        id=uuid4(),
        company_name=company_name,
        source="test",
        city=city,
        status=LeadStatus.SCORED,
    )


def create_test_profile(
    lead_id,
    segment: IndustrySegment,
    city: str | None = None,
) -> CompanyProfile:
    """Create test company profile."""
    return CompanyProfile(
        id=uuid4(),
        lead_id=lead_id,
        industry=segment,
        city=city,
        active_vacancies_count=10,
        personalization_hooks=[
            "Активно нанимают в текущем месяце",
            "Открыли 5 новых точек",
        ],
    )


def create_test_segment(
    lead_id,
    segment: IndustrySegment,
) -> LeadSegment:
    """Create test segment."""
    # Default values by segment
    segment_data = {
        IndustrySegment.RETAIL: {
            "pain_statement": "Сезонные пики, текучка кассиров",
            "value_proposition": "Закрываем кассиров за 48 часов",
            "proof_point": "Работаем с сетями от 50 точек",
            "communication_angle": "speed",
            "suggested_cta": "Имеет смысл обсудить?",
        },
        IndustrySegment.HORECA: {
            "pain_statement": "Невыходы 25-30%, срочные замены",
            "value_proposition": "Повара и официанты с рейтингом надёжности",
            "proof_point": "Явка 94% vs 70% по рынку",
            "communication_angle": "reliability",
            "suggested_cta": "Актуально для вас?",
        },
        IndustrySegment.LOGISTICS: {
            "pain_statement": "Пиковые нагрузки, масштабирование",
            "value_proposition": "200 курьеров в неделю",
            "proof_point": "Масштабируем за 24 часа",
            "communication_angle": "scale",
            "suggested_cta": "Стоит обсудить?",
        },
    }

    data = segment_data.get(segment, segment_data[IndustrySegment.RETAIL])

    return LeadSegment(
        id=uuid4(),
        lead_id=lead_id,
        segment=segment,
        priority=LeadPriority.HIGH,
        tone="professional",
        offer_type="general",
        **data,
    )


def create_test_contact(
    lead_id,
    name: str = "Анна",
) -> EmployerContact:
    """Create test contact."""
    return EmployerContact(
        id=uuid4(),
        lead_id=lead_id,
        full_name=name,
        first_name=name,
        email="test@example.com",
    )


async def test_single_email(
    company_name: str,
    segment: IndustrySegment,
    email_type: EmailType,
    city: str | None,
    contact_name: str,
    use_mock: bool,
) -> None:
    """Test single email generation."""
    print(f"\n{'='*60}")
    print(f"Generating {email_type.value} for {company_name}")
    print(f"Segment: {segment.value}, City: {city or 'N/A'}")
    print(f"{'='*60}\n")

    # Create test objects
    lead = create_test_lead(company_name, city)
    profile = create_test_profile(lead.id, segment, city)
    segment_obj = create_test_segment(lead.id, segment)
    contact = create_test_contact(lead.id, contact_name)

    # Create engine
    llm_router = LLMRouter(use_mock=use_mock)
    engine = EmailIntelligenceEngine(llm_router)

    print(f"Available LLM providers: {llm_router.get_available_providers()}")
    print(f"Using mock: {use_mock}\n")

    # Generate email
    result = await engine.generate_email(
        lead=lead,
        profile=profile,
        segment=segment_obj,
        contact=contact,
        email_type=email_type,
    )

    # Print result
    if result.success and result.email:
        print("SUCCESS!\n")
        print(f"Subject: {result.email.subject}")
        print(f"\nBody:\n{result.email.body}")
        print(f"\n--- Quality Gate ---")
        if result.quality_result:
            print(f"Passed: {result.quality_result.passed}")
            print(f"Word count: {result.quality_result.word_count}")
            print(f"Subject length: {result.quality_result.subject_length}")
            if result.quality_result.issues:
                print(f"Issues: {result.quality_result.issues}")
        print(f"\nGeneration model: {result.generation_model}")
    else:
        print("FAILED!\n")
        print(f"Error: {result.error}")
        if result.quality_result and result.quality_result.issues:
            print(f"Quality issues: {result.quality_result.issues}")


async def test_full_sequence(
    company_name: str,
    segment: IndustrySegment,
    city: str | None,
    contact_name: str,
    use_mock: bool,
) -> None:
    """Test full email sequence generation."""
    print(f"\n{'='*60}")
    print(f"Generating FULL SEQUENCE for {company_name}")
    print(f"Segment: {segment.value}, City: {city or 'N/A'}")
    print(f"{'='*60}\n")

    # Create test objects
    lead = create_test_lead(company_name, city)
    profile = create_test_profile(lead.id, segment, city)
    segment_obj = create_test_segment(lead.id, segment)
    contact = create_test_contact(lead.id, contact_name)

    # Create engine
    llm_router = LLMRouter(use_mock=use_mock)
    engine = EmailIntelligenceEngine(llm_router)

    # Generate sequence
    results = await engine.generate_sequence(
        lead=lead,
        profile=profile,
        segment=segment_obj,
        contact=contact,
    )

    # Print results
    for i, result in enumerate(results, 1):
        email_type = [
            EmailType.FIRST_TOUCH,
            EmailType.FOLLOWUP_1,
            EmailType.FOLLOWUP_2,
            EmailType.BREAKUP,
        ][i - 1]

        print(f"\n--- Email {i}: {email_type.value} ---")

        if result.success and result.email:
            print(f"Subject: {result.email.subject}")
            print(f"Body:\n{result.email.body[:300]}...")
            print(f"Quality passed: {result.quality_result.passed if result.quality_result else 'N/A'}")
        else:
            print(f"FAILED: {result.error}")

    # Summary
    passed = sum(1 for r in results if r.success)
    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed}/{len(results)} emails generated successfully")
    print(f"{'='*60}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test email generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--company",
        required=True,
        help="Company name",
    )
    parser.add_argument(
        "--segment",
        choices=[s.value for s in IndustrySegment],
        default="retail",
        help="Industry segment",
    )
    parser.add_argument(
        "--type",
        choices=[t.value for t in EmailType],
        default="first_touch",
        help="Email type",
    )
    parser.add_argument(
        "--city",
        help="City name",
    )
    parser.add_argument(
        "--contact",
        default="Анна",
        help="Contact name",
    )
    parser.add_argument(
        "--full-sequence",
        action="store_true",
        help="Generate full email sequence",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock LLM provider",
    )

    args = parser.parse_args()

    segment = IndustrySegment(args.segment)
    email_type = EmailType(args.type)

    if args.full_sequence:
        asyncio.run(
            test_full_sequence(
                company_name=args.company,
                segment=segment,
                city=args.city,
                contact_name=args.contact,
                use_mock=args.mock,
            )
        )
    else:
        asyncio.run(
            test_single_email(
                company_name=args.company,
                segment=segment,
                email_type=email_type,
                city=args.city,
                contact_name=args.contact,
                use_mock=args.mock,
            )
        )


if __name__ == "__main__":
    main()
