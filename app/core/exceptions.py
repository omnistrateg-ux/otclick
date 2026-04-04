"""Domain exceptions."""

from app.models.enums import LeadStatus


class OtclickError(Exception):
    """Base exception for all domain errors."""

    def __init__(self, message: str, code: str | None = None) -> None:
        self.message = message
        self.code = code or "OTCLICK_ERROR"
        super().__init__(message)


class InvalidStateTransitionError(OtclickError):
    """Raised when an invalid state transition is attempted."""

    def __init__(
        self,
        from_status: LeadStatus,
        to_status: LeadStatus,
        message: str | None = None,
    ) -> None:
        self.from_status = from_status
        self.to_status = to_status
        default_message = (
            f"Invalid transition from {from_status.value} to {to_status.value}"
        )
        super().__init__(
            message=message or default_message,
            code="INVALID_STATE_TRANSITION",
        )


class LeadNotFoundError(OtclickError):
    """Raised when a lead is not found."""

    def __init__(self, lead_id: str) -> None:
        super().__init__(
            message=f"Lead not found: {lead_id}",
            code="LEAD_NOT_FOUND",
        )


class ContactNotFoundError(OtclickError):
    """Raised when a contact is not found."""

    def __init__(self, contact_id: str) -> None:
        super().__init__(
            message=f"Contact not found: {contact_id}",
            code="CONTACT_NOT_FOUND",
        )


class DuplicateLeadError(OtclickError):
    """Raised when a duplicate lead is detected."""

    def __init__(self, existing_lead_id: str, reason: str) -> None:
        self.existing_lead_id = existing_lead_id
        super().__init__(
            message=f"Duplicate lead detected: {reason}. Existing: {existing_lead_id}",
            code="DUPLICATE_LEAD",
        )


class EnrichmentError(OtclickError):
    """Raised when enrichment fails."""

    def __init__(self, lead_id: str, reason: str) -> None:
        super().__init__(
            message=f"Enrichment failed for {lead_id}: {reason}",
            code="ENRICHMENT_FAILED",
        )


class EmailGenerationError(OtclickError):
    """Raised when email generation fails."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            message=f"Email generation failed: {reason}",
            code="EMAIL_GENERATION_FAILED",
        )


class QualityGateError(OtclickError):
    """Raised when email fails quality gate."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__(
            message=f"Quality gate failed: {', '.join(issues)}",
            code="QUALITY_GATE_FAILED",
        )


class EmailDeliveryError(OtclickError):
    """Raised when email delivery fails."""

    def __init__(self, reason: str, bounce_type: str | None = None) -> None:
        self.bounce_type = bounce_type
        super().__init__(
            message=f"Email delivery failed: {reason}",
            code="EMAIL_DELIVERY_FAILED",
        )


class LLMProviderError(OtclickError):
    """Raised when LLM provider fails."""

    def __init__(self, provider: str, reason: str) -> None:
        self.provider = provider
        super().__init__(
            message=f"LLM provider {provider} failed: {reason}",
            code="LLM_PROVIDER_ERROR",
        )


class RateLimitError(OtclickError):
    """Raised when rate limit is exceeded."""

    def __init__(self, limit_type: str, retry_after: int | None = None) -> None:
        self.limit_type = limit_type
        self.retry_after = retry_after
        super().__init__(
            message=f"Rate limit exceeded: {limit_type}",
            code="RATE_LIMIT_EXCEEDED",
        )


class ComplianceError(OtclickError):
    """Raised for compliance violations."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            message=f"Compliance violation: {reason}",
            code="COMPLIANCE_VIOLATION",
        )
