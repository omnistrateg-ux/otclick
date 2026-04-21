"""Sales API endpoints.

API для B2B sales агента: генерация ответов, анализ, база знаний.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.sales_agent import SalesAgent
from app.llm.router import LLMRouter
from app.models.domain import AgentTask, EmployerLead
from app.models.enums import ReplyIntent
from app.services.sales_knowledge_base import (
    ConversationStage,
    ObjectionType,
    sales_knowledge_base,
)
from app.services.sales_strategy import (
    ConversationContext,
    sales_strategy_service,
)
from app.storage.database import get_session
from app.tools.analysis_tools import classify_reply_rule_based

router = APIRouter(prefix="/sales", tags=["sales"])


# Request/Response models
class PreviousEmail(BaseModel):
    """Previous email in the conversation."""

    subject: str
    body: str


class GenerateResponseRequest(BaseModel):
    """Request to generate sales response."""

    lead_id: str = Field(..., description="Lead ID (UUID string)")
    company_name: str = Field(..., description="Company name")
    contact_name: str = Field(..., description="Contact person name")
    industry: str = Field(default="other", description="Industry segment")
    city: str | None = Field(default=None, description="City")
    reply_text: str | None = Field(default=None, description="Reply text to respond to")
    previous_emails: list[PreviousEmail] = Field(
        default_factory=list, description="Previous emails in thread"
    )
    emails_sent_count: int = Field(default=0, description="Number of emails sent")


class EmailResponse(BaseModel):
    """Generated email."""

    subject: str
    body: str


class StrategyInfo(BaseModel):
    """Strategy information."""

    stage: str
    strategy: str
    cta_type: str
    tone: str
    handoff_recommended: bool
    reasoning: str


class AnalysisInfo(BaseModel):
    """Reply analysis information."""

    reply_intent: str | None
    intent_confidence: float
    objection_type: str | None


class QualityInfo(BaseModel):
    """Quality validation info."""

    passed: bool
    issues: list[str]
    word_count: int | None = None
    subject_length: int | None = None


class GenerateResponseResponse(BaseModel):
    """Response with generated email."""

    success: bool
    email: EmailResponse | None = None
    strategy: StrategyInfo | None = None
    analysis: AnalysisInfo | None = None
    quality: QualityInfo | None = None
    internal_notes: str | None = None
    error: str | None = None


class AnalyzeReplyRequest(BaseModel):
    """Request to analyze reply."""

    reply_text: str = Field(..., description="Reply text to analyze")


class AnalyzeReplyResponse(BaseModel):
    """Response with reply analysis."""

    intent: str
    intent_confidence: float
    objection_type: str | None
    objection_handler: dict | None = None
    is_positive: bool
    is_negative: bool
    recommended_stage: str


class KnowledgeQueryResponse(BaseModel):
    """Response with knowledge base data."""

    industry_insight: dict | None = None
    objection_handler: dict | None = None
    all_industries: list[str] | None = None
    all_objection_types: list[str] | None = None


class ManagerContactResponse(BaseModel):
    """Manager contact information."""

    name: str
    phone: str
    email: str
    role: str


# Endpoints
@router.post("/generate-response", response_model=GenerateResponseResponse)
async def generate_sales_response(
    request: GenerateResponseRequest,
    db: AsyncSession = Depends(get_session),
) -> GenerateResponseResponse:
    """Generate sales response based on conversation context.

    Takes lead info, previous emails, and optional reply text.
    Returns generated email with strategy and quality info.
    """
    try:
        # Create LLM router
        llm_router = LLMRouter()

        # Create agent
        agent = SalesAgent(llm_router=llm_router, db=db)

        # Build lead object
        lead = EmployerLead(
            id=UUID(request.lead_id),
            company_name=request.company_name,
            source="api",
            city=request.city,
        )

        # Build task
        task = AgentTask(
            lead_id=lead.id,
            agent_name="sales",
            task_type="generate_response",
            input_data={
                "lead": lead.model_dump(mode="json"),
                "contact_name": request.contact_name,
                "reply_text": request.reply_text,
                "previous_emails": [e.model_dump() for e in request.previous_emails],
                "emails_sent_count": request.emails_sent_count,
                "industry": request.industry,
                "city": request.city,
            },
        )

        # Execute agent
        result = await agent.execute(task)

        if not result.success:
            return GenerateResponseResponse(
                success=False,
                error=result.error,
            )

        return GenerateResponseResponse(
            success=True,
            email=EmailResponse(**result.data.get("email", {})),
            strategy=StrategyInfo(**result.data.get("strategy", {})),
            analysis=AnalysisInfo(**result.data.get("analysis", {})),
            quality=QualityInfo(**result.data.get("quality", {})),
            internal_notes=result.data.get("internal_notes"),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-reply", response_model=AnalyzeReplyResponse)
async def analyze_reply(request: AnalyzeReplyRequest) -> AnalyzeReplyResponse:
    """Analyze reply text and return intent classification.

    Detects intent, objection type, and recommends conversation stage.
    """
    # Classify intent
    intent, confidence = classify_reply_rule_based(request.reply_text)

    # Detect objection
    objection_type = sales_knowledge_base.detect_objection(request.reply_text)

    # Get objection handler if found
    objection_handler = None
    if objection_type:
        handler = sales_knowledge_base.get_objection_handler(objection_type)
        objection_handler = {
            "response_template": handler.response_template,
            "tone": handler.tone,
            "follow_up_cta": handler.follow_up_cta,
        }

    # Determine if positive/negative
    is_positive = intent in {
        ReplyIntent.SOFT_INTEREST,
        ReplyIntent.REQUEST_DETAILS,
        ReplyIntent.STRONG_INTEREST,
        ReplyIntent.READY_TO_CALL,
    }
    is_negative = intent in {
        ReplyIntent.REFUSAL,
        ReplyIntent.UNSUBSCRIBE,
    }

    # Get recommended stage
    context = ConversationContext(
        lead_id=UUID("00000000-0000-0000-0000-000000000000"),
        company_name="",
        contact_name="",
        industry="other",
        reply_text=request.reply_text,
        reply_intent=intent,
        intent_confidence=confidence,
        objection_type=objection_type,
        emails_sent_count=1,  # Assume at least one email sent
    )
    strategy = sales_strategy_service.determine_strategy(context)

    return AnalyzeReplyResponse(
        intent=intent.value,
        intent_confidence=confidence,
        objection_type=objection_type.value if objection_type else None,
        objection_handler=objection_handler,
        is_positive=is_positive,
        is_negative=is_negative,
        recommended_stage=strategy.stage.value,
    )


@router.get("/knowledge", response_model=KnowledgeQueryResponse)
async def query_knowledge_base(
    industry: str | None = None,
    objection: str | None = None,
) -> KnowledgeQueryResponse:
    """Query sales knowledge base.

    Get industry insights, objection handlers, or list all available options.
    """
    response = KnowledgeQueryResponse()

    # Get industry insight
    if industry:
        insight = sales_knowledge_base.get_industry_insight(industry)
        if insight:
            response.industry_insight = {
                "industry": insight.industry,
                "pain_points": insight.pain_points,
                "typical_roles": insight.typical_roles,
                "value_angles": insight.value_angles,
                "proof_points": insight.proof_points,
            }

    # Get objection handler
    if objection:
        try:
            objection_type = ObjectionType(objection)
            handler = sales_knowledge_base.get_objection_handler(objection_type)
            response.objection_handler = {
                "objection_type": handler.objection_type.value,
                "trigger_phrases": handler.trigger_phrases,
                "response_template": handler.response_template,
                "tone": handler.tone,
                "follow_up_cta": handler.follow_up_cta,
            }
        except ValueError:
            pass  # Invalid objection type, ignore

    # If no specific query, return all available options
    if not industry and not objection:
        response.all_industries = sales_knowledge_base.get_all_industries()
        response.all_objection_types = [
            o.value for o in sales_knowledge_base.get_all_objection_types()
        ]

    return response


@router.get("/manager-contact", response_model=ManagerContactResponse)
async def get_manager_contact() -> ManagerContactResponse:
    """Get manager contact for handoff."""
    contact = sales_knowledge_base.get_manager_contact()
    return ManagerContactResponse(
        name=contact.name,
        phone=contact.phone,
        email=contact.email,
        role=contact.role,
    )


@router.get("/stages")
async def list_conversation_stages() -> dict[str, list[str]]:
    """List all conversation stages."""
    return {
        "stages": [s.value for s in ConversationStage],
    }


@router.get("/objection-types")
async def list_objection_types() -> dict[str, list[str]]:
    """List all objection types."""
    return {
        "objection_types": [o.value for o in ObjectionType],
    }
