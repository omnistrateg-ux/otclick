"""Models module - enums, domain objects, and ORM models."""

from app.models.enums import (
    ContactRole,
    EmailType,
    HiringIntensity,
    IndustrySegment,
    LeadPriority,
    LeadStatus,
    LLMTaskType,
    ReplyIntent,
)

__all__ = [
    "LeadStatus",
    "IndustrySegment",
    "ContactRole",
    "ReplyIntent",
    "EmailType",
    "HiringIntensity",
    "LeadPriority",
    "LLMTaskType",
]
