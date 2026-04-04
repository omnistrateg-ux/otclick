"""Email Intelligence Engine module.

Содержит генерацию писем, quality gate, delivery.
"""

from app.email.delivery import EmailDelivery
from app.email.engine import EmailIntelligenceEngine
from app.email.quality_gate import QualityGate, QualityResult
from app.email.templates import SEGMENT_CONTEXTS, SegmentContext

__all__ = [
    "EmailIntelligenceEngine",
    "EmailDelivery",
    "QualityGate",
    "QualityResult",
    "SegmentContext",
    "SEGMENT_CONTEXTS",
]
