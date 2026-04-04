"""Agents module."""

from app.agents.base import AgentResult, BaseAgent
from app.agents.discovery_agent import DiscoveryAgent
from app.agents.email_copy_agent import EmailCopyAgent
from app.agents.enrichment_agent import EnrichmentAgent
from app.agents.followup_agent import FollowUpAgent
from app.agents.handoff_agent import HandoffAgent
from app.agents.qualification_agent import QualificationAgent
from app.agents.response_agent import ResponseAgent
from app.agents.scoring_agent import ScoringAgent

__all__ = [
    "BaseAgent",
    "AgentResult",
    "DiscoveryAgent",
    "EnrichmentAgent",
    "ScoringAgent",
    "EmailCopyAgent",
    "FollowUpAgent",
    "ResponseAgent",
    "QualificationAgent",
    "HandoffAgent",
]
