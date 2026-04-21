"""Account-Based Outreach API endpoints.

Multi-contact outreach strategies with stop rules.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.account_outreach import AccountOutreachService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/outreach", tags=["outreach"])


# ============================================================================
# Request/Response Models
# ============================================================================


class InitializeAccountRequest(BaseModel):
    """Request to initialize account-based outreach."""

    account_id: str
    contact_ids: list[str] = Field(..., min_length=1, max_length=10)
    campaign_id: str | None = None
    max_contacts: int | None = None
    days_between_contacts: int | None = None
    max_touches_per_contact: int | None = None


class RecordTouchRequest(BaseModel):
    """Request to record a touch."""

    account_id: str
    contact_id: str
    touch_type: str = "email"
    message_id: str | None = None


class HandleReplyRequest(BaseModel):
    """Request to handle a reply."""

    account_id: str
    contact_id: str
    is_positive: bool = False
    message_id: str | None = None


class HandleBounceRequest(BaseModel):
    """Request to handle a bounce."""

    account_id: str
    contact_id: str
    bounce_type: str = "hard"


class HandleOptOutRequest(BaseModel):
    """Request to handle an opt-out."""

    account_id: str
    contact_id: str
    reason: str = "unsubscribed"


class AccountStateResponse(BaseModel):
    """Account outreach state response."""

    lead_id: str
    status: str
    stop_reason: str | None
    total_touches: int
    total_bounces: int
    has_reply: bool
    has_positive_reply: bool
    started_at: str | None
    stopped_at: str | None
    contact_count: int


class NextTouchResponse(BaseModel):
    """Next touch recommendation response."""

    should_touch: bool
    contact_id: str | None
    touch_number: int
    recommended_time: str | None
    reason: str
    days_until: int = 0


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/account/initialize")
async def initialize_account(
    request: InitializeAccountRequest,
) -> dict[str, Any]:
    """Initialize account-based outreach for a company.

    Sets up multi-contact touch strategy with stop rules.

    Args:
        request: Account initialization config

    Returns:
        Account state
    """
    service = AccountOutreachService()

    # Build priorities from contact order
    contact_priorities = {cid: len(request.contact_ids) - i for i, cid in enumerate(request.contact_ids)}

    state = await service.initialize_account(
        lead_id=request.account_id,
        contact_ids=request.contact_ids,
        contact_priorities=contact_priorities,
    )

    return state.to_dict()


@router.get("/account/{lead_id}")
async def get_account_state(
    lead_id: str,
) -> AccountStateResponse:
    """Get current account outreach state.

    Args:
        lead_id: Lead/account ID

    Returns:
        Account state
    """
    service = AccountOutreachService()
    state = await service.get_account_state(lead_id)

    if state.status == service.AccountStatus.NOT_STARTED if hasattr(service, 'AccountStatus') else state.status.value == "not_started":
        raise HTTPException(404, f"Account {lead_id} not found")

    return AccountStateResponse(
        lead_id=state.lead_id,
        status=state.status.value,
        stop_reason=state.stop_reason.value if state.stop_reason else None,
        total_touches=state.total_touches,
        total_bounces=state.total_bounces,
        has_reply=state.has_reply,
        has_positive_reply=state.has_positive_reply,
        started_at=state.started_at.isoformat() if state.started_at else None,
        stopped_at=state.stopped_at.isoformat() if state.stopped_at else None,
        contact_count=len(state.contacts),
    )


@router.get("/account/{lead_id}/next-touch")
async def get_next_touch(
    lead_id: str,
) -> NextTouchResponse:
    """Get next touch recommendation for an account.

    Args:
        lead_id: Lead/account ID

    Returns:
        Next touch recommendation
    """
    service = AccountOutreachService()
    recommendation = await service.get_next_touch(lead_id)

    return NextTouchResponse(
        should_touch=recommendation.should_touch,
        contact_id=recommendation.contact_id,
        touch_number=recommendation.touch_number,
        recommended_time=recommendation.recommended_time.isoformat() if recommendation.recommended_time else None,
        reason=recommendation.reason,
        days_until=recommendation.days_until,
    )


@router.post("/account/touch")
async def record_touch(
    request: RecordTouchRequest,
) -> dict[str, Any]:
    """Record a touch (email sent) for a contact.

    Args:
        request: Touch details

    Returns:
        Updated state
    """
    service = AccountOutreachService()

    state = await service.record_touch(
        lead_id=request.account_id,
        contact_id=request.contact_id,
        email_id=request.message_id,
    )

    return state.to_dict()


@router.post("/account/reply")
async def handle_reply(
    request: HandleReplyRequest,
) -> dict[str, Any]:
    """Handle a reply from a contact.

    If stop_on_any_reply is enabled, stops all outreach to this account.

    Args:
        request: Reply details

    Returns:
        Updated state
    """
    service = AccountOutreachService()

    state = await service.handle_reply(
        lead_id=request.account_id,
        contact_id=request.contact_id,
        is_positive=request.is_positive,
    )

    return state.to_dict()


@router.post("/account/bounce")
async def handle_bounce(
    request: HandleBounceRequest,
) -> dict[str, Any]:
    """Handle a bounce for a contact.

    May stop account if bounce threshold is reached.

    Args:
        request: Bounce details

    Returns:
        Updated state
    """
    service = AccountOutreachService()

    is_hard = request.bounce_type == "hard"
    state = await service.handle_bounce(
        lead_id=request.account_id,
        contact_id=request.contact_id,
        is_hard_bounce=is_hard,
    )

    return state.to_dict()


@router.post("/account/opt-out")
async def handle_opt_out(
    request: HandleOptOutRequest,
) -> dict[str, Any]:
    """Handle an opt-out from a contact.

    Stops all outreach to this account.

    Args:
        request: Opt-out details

    Returns:
        Updated state
    """
    service = AccountOutreachService()

    state = await service.handle_opt_out(
        lead_id=request.account_id,
        contact_id=request.contact_id,
    )

    return state.to_dict()


@router.get("/account/{lead_id}/contacts")
async def get_account_contacts(
    lead_id: str,
) -> list[dict[str, Any]]:
    """Get all contacts for an account with their touch status.

    Args:
        lead_id: Lead/account ID

    Returns:
        List of contact statuses
    """
    service = AccountOutreachService()
    contacts = await service.get_contact_statuses(lead_id)

    return contacts  # Already a list of dicts


@router.get("/accounts/active")
async def get_active_accounts(
    campaign_id: str = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Get all active account outreach campaigns.

    Args:
        campaign_id: Filter by campaign
        limit: Maximum results

    Returns:
        List of active account states
    """
    service = AccountOutreachService()
    accounts = await service.get_active_accounts(campaign_id=campaign_id, limit=limit)

    return [a.to_dict() for a in accounts]


@router.post("/account/{lead_id}/stop")
async def stop_account_outreach(
    lead_id: str,
    reason: str = Query(default="manual"),
) -> dict[str, Any]:
    """Manually stop outreach to an account.

    Args:
        lead_id: Lead/account ID
        reason: Stop reason

    Returns:
        Updated state
    """
    from app.services.account_outreach import StopReason

    service = AccountOutreachService()

    # Map string reason to enum
    reason_map = {
        "manual": StopReason.MANUAL,
        "reply_received": StopReason.REPLY_RECEIVED,
        "opt_out": StopReason.OPT_OUT,
        "bounce_limit": StopReason.BOUNCE_LIMIT,
    }
    stop_reason = reason_map.get(reason, StopReason.MANUAL)

    state = await service.stop_account(lead_id, stop_reason)
    return state.to_dict()


@router.get("/stats")
async def get_outreach_stats(
    campaign_id: str = Query(default=None),
    days: int = Query(default=7, ge=1, le=90),
) -> dict[str, Any]:
    """Get account-based outreach statistics.

    Args:
        campaign_id: Filter by campaign
        days: Days to analyze

    Returns:
        Outreach statistics
    """
    service = AccountOutreachService()
    stats = await service.get_outreach_stats(campaign_id=campaign_id, days=days)

    return stats
