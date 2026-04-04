"""Email Intelligence Engine.

Ядро генерации писем из ARCHITECTURE.md раздел 7.1.
"""

import json
import logging

from app.email.prompts import build_email_prompt
from app.email.quality_gate import QualityGate, QualityResult
from app.email.templates import (
    CTA_VARIANTS,
    get_max_words,
    get_segment_context,
)
from app.llm.models import LLMRequest
from app.llm.router import LLMRouter
from app.models.domain import (
    CompanyProfile,
    EmailMessage,
    EmployerContact,
    EmployerLead,
    LeadSegment,
)
from app.models.enums import EmailType, LLMTaskType

logger = logging.getLogger(__name__)


class EmailGenerationResult:
    """Result of email generation."""

    def __init__(
        self,
        success: bool,
        email: EmailMessage | None = None,
        quality_result: QualityResult | None = None,
        error: str | None = None,
        generation_model: str | None = None,
    ) -> None:
        self.success = success
        self.email = email
        self.quality_result = quality_result
        self.error = error
        self.generation_model = generation_model


class EmailIntelligenceEngine:
    """Core email generation engine.

    Генерирует персонализированные письма через LLM,
    валидирует через Quality Gate.
    """

    PROMPT_VERSION = "v1.0"
    MAX_RETRIES = 3

    def __init__(
        self,
        llm_router: LLMRouter,
        quality_gate: QualityGate | None = None,
    ) -> None:
        """Initialize engine.

        Args:
            llm_router: Router for LLM calls
            quality_gate: Quality gate for validation (optional)
        """
        self.llm = llm_router
        self.quality_gate = quality_gate or QualityGate()

    async def generate_email(
        self,
        lead: EmployerLead,
        profile: CompanyProfile,
        segment: LeadSegment,
        contact: EmployerContact,
        email_type: EmailType,
        sequence_id: str | None = None,
        previous_emails: list[dict] | None = None,
    ) -> EmailGenerationResult:
        """Generate a single email.

        Args:
            lead: Lead to generate email for
            profile: Company profile
            segment: Lead segment
            contact: Contact person
            email_type: Type of email
            sequence_id: Email sequence ID
            previous_emails: Previous emails in sequence

        Returns:
            Generation result with email or error
        """
        # Build prompts
        system_prompt, user_prompt = build_email_prompt(
            email_type=email_type,
            segment=segment.segment,
            company_name=lead.company_name,
            contact_name=contact.first_name or contact.full_name,
            city=lead.city or profile.city,
            pain_statement=segment.pain_statement,
            value_proposition=segment.value_proposition,
            proof_point=segment.proof_point,
            personalization_hooks=profile.personalization_hooks,
            previous_emails=previous_emails,
        )

        # Try generation with retries
        last_error: str | None = None
        generation_model: str | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                # Generate via LLM
                request = LLMRequest(
                    task_type=LLMTaskType.EMAIL_GENERATION,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    json_mode=True,
                    agent_name="email_engine",
                )

                response = await self.llm.complete(request)
                generation_model = response.model

                # Parse response
                email_data = self._parse_response(response.content)
                if not email_data:
                    last_error = "Failed to parse LLM response as JSON"
                    continue

                subject = email_data.get("subject", "")
                body = email_data.get("body", "")

                if not subject or not body:
                    last_error = "Missing subject or body in response"
                    continue

                # Validate through quality gate
                quality_result = self.quality_gate.validate(
                    subject=subject,
                    body=body,
                    email_type=email_type,
                    lead=lead,
                )

                # Create email message
                from uuid import uuid4

                email = EmailMessage(
                    id=uuid4(),
                    sequence_id=uuid4() if not sequence_id else uuid4(),
                    lead_id=lead.id,
                    contact_id=contact.id,
                    email_type=email_type,
                    subject=subject,
                    body=body,
                    step_number=self._get_step_number(email_type),
                    generation_model=generation_model,
                    generation_prompt_version=self.PROMPT_VERSION,
                    quality_gate_passed=quality_result.passed,
                    quality_gate_issues=quality_result.issues,
                )

                return EmailGenerationResult(
                    success=quality_result.passed,
                    email=email,
                    quality_result=quality_result,
                    generation_model=generation_model,
                    error=None if quality_result.passed else f"Quality gate failed: {quality_result.issues}",
                )

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Email generation attempt {attempt + 1} failed: {e}"
                )
                continue

        return EmailGenerationResult(
            success=False,
            email=None,
            quality_result=None,
            generation_model=generation_model,
            error=last_error or "Unknown error",
        )

    async def generate_sequence(
        self,
        lead: EmployerLead,
        profile: CompanyProfile,
        segment: LeadSegment,
        contact: EmployerContact,
    ) -> list[EmailGenerationResult]:
        """Generate full email sequence.

        Generates all 4 emails: first_touch, followup_1, followup_2, breakup.

        Args:
            lead: Lead
            profile: Company profile
            segment: Lead segment
            contact: Contact person

        Returns:
            List of generation results
        """
        results: list[EmailGenerationResult] = []
        previous_emails: list[dict] = []

        email_types = [
            EmailType.FIRST_TOUCH,
            EmailType.FOLLOWUP_1,
            EmailType.FOLLOWUP_2,
            EmailType.BREAKUP,
        ]

        for email_type in email_types:
            result = await self.generate_email(
                lead=lead,
                profile=profile,
                segment=segment,
                contact=contact,
                email_type=email_type,
                previous_emails=previous_emails if previous_emails else None,
            )

            results.append(result)

            # Add to previous for context
            if result.success and result.email:
                previous_emails.append({
                    "subject": result.email.subject,
                    "body": result.email.body,
                })

        return results

    async def regenerate_email(
        self,
        email: EmailMessage,
        lead: EmployerLead,
        profile: CompanyProfile,
        segment: LeadSegment,
        contact: EmployerContact,
        previous_emails: list[dict] | None = None,
    ) -> EmailGenerationResult:
        """Regenerate email that failed quality gate.

        Args:
            email: Original email that failed
            lead: Lead
            profile: Company profile
            segment: Lead segment
            contact: Contact person
            previous_emails: Previous emails in sequence

        Returns:
            New generation result
        """
        return await self.generate_email(
            lead=lead,
            profile=profile,
            segment=segment,
            contact=contact,
            email_type=email.email_type,
            sequence_id=str(email.sequence_id),
            previous_emails=previous_emails,
        )

    def _parse_response(self, content: str) -> dict | None:
        """Parse LLM response as JSON.

        Args:
            content: LLM response content

        Returns:
            Parsed dict or None
        """
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            try:
                return json.loads(content.strip())
            except json.JSONDecodeError:
                return None

    def _get_step_number(self, email_type: EmailType) -> int:
        """Get step number for email type.

        Args:
            email_type: Type of email

        Returns:
            Step number (1-4)
        """
        return {
            EmailType.FIRST_TOUCH: 1,
            EmailType.FOLLOWUP_1: 2,
            EmailType.FOLLOWUP_2: 3,
            EmailType.BREAKUP: 4,
        }.get(email_type, 1)

    def get_suggested_cta(self, email_type: EmailType) -> str:
        """Get suggested CTA for email type.

        Args:
            email_type: Type of email

        Returns:
            Suggested CTA text
        """
        variants = CTA_VARIANTS.get(email_type, CTA_VARIANTS[EmailType.FIRST_TOUCH])
        return variants[0] if variants else "Имеет смысл обсудить?"
