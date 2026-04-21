"""Approval Gates Service.

Multi-step approval workflow for risky actions.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any
import uuid

UTC = timezone.utc

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    """Status of approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class RiskLevel(str, Enum):
    """Risk level of action."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionCategory(str, Enum):
    """Category of risky action."""

    DATA_DELETION = "data_deletion"
    MASS_EMAIL = "mass_email"
    SYSTEM_CONFIG = "system_config"
    USER_ACCESS = "user_access"
    DEPLOYMENT = "deployment"
    DATABASE = "database"
    INTEGRATION = "integration"
    FINANCIAL = "financial"


@dataclass
class ApprovalRule:
    """Rule defining approval requirements."""

    id: str
    category: ActionCategory
    risk_level: RiskLevel
    required_approvers: int
    allowed_approvers: list[str]  # Roles or user IDs
    auto_expire_hours: int
    require_reason: bool
    notify_on_request: bool
    enabled: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "risk_level": self.risk_level.value,
            "required_approvers": self.required_approvers,
            "allowed_approvers": self.allowed_approvers,
            "auto_expire_hours": self.auto_expire_hours,
            "require_reason": self.require_reason,
            "notify_on_request": self.notify_on_request,
            "enabled": self.enabled,
        }


@dataclass
class ApprovalRequest:
    """Request for approval."""

    id: str
    action: str
    category: ActionCategory
    risk_level: RiskLevel
    requester: str
    status: ApprovalStatus
    created_at: datetime
    expires_at: datetime
    required_approvers: int
    current_approvers: list[str]
    reason: str
    context: dict[str, Any]
    decision_at: datetime | None = None
    decision_by: str | None = None
    rejection_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "category": self.category.value,
            "risk_level": self.risk_level.value,
            "requester": self.requester,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "required_approvers": self.required_approvers,
            "current_approvers": self.current_approvers,
            "reason": self.reason,
            "context": self.context,
            "decision_at": self.decision_at.isoformat() if self.decision_at else None,
            "decision_by": self.decision_by,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class ApprovalDecision:
    """Individual approval decision."""

    request_id: str
    approver: str
    decision: str  # approve/reject
    reason: str | None
    decided_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "approver": self.approver,
            "decision": self.decision,
            "reason": self.reason,
            "decided_at": self.decided_at.isoformat(),
        }


class ApprovalGatesService:
    """Service for approval gates.

    Features:
    - Define approval rules per action category
    - Request approvals
    - Multi-approver support
    - Auto-expiration
    - Audit trail
    """

    RULES_KEY = "approval:rules"
    REQUESTS_KEY = "approval:requests"
    DECISIONS_KEY = "approval:decisions"

    # Default rules
    DEFAULT_RULES = [
        {
            "category": ActionCategory.DATA_DELETION,
            "risk_level": RiskLevel.CRITICAL,
            "required_approvers": 2,
            "allowed_approvers": ["admin", "owner"],
            "auto_expire_hours": 24,
            "require_reason": True,
            "notify_on_request": True,
        },
        {
            "category": ActionCategory.MASS_EMAIL,
            "risk_level": RiskLevel.HIGH,
            "required_approvers": 1,
            "allowed_approvers": ["admin", "marketing"],
            "auto_expire_hours": 48,
            "require_reason": True,
            "notify_on_request": True,
        },
        {
            "category": ActionCategory.SYSTEM_CONFIG,
            "risk_level": RiskLevel.HIGH,
            "required_approvers": 1,
            "allowed_approvers": ["admin", "ops"],
            "auto_expire_hours": 24,
            "require_reason": False,
            "notify_on_request": True,
        },
        {
            "category": ActionCategory.DEPLOYMENT,
            "risk_level": RiskLevel.MEDIUM,
            "required_approvers": 1,
            "allowed_approvers": ["admin", "developer", "ops"],
            "auto_expire_hours": 12,
            "require_reason": False,
            "notify_on_request": True,
        },
        {
            "category": ActionCategory.DATABASE,
            "risk_level": RiskLevel.CRITICAL,
            "required_approvers": 2,
            "allowed_approvers": ["admin", "dba"],
            "auto_expire_hours": 24,
            "require_reason": True,
            "notify_on_request": True,
        },
    ]

    def __init__(self) -> None:
        """Initialize service."""
        pass

    async def initialize_defaults(self) -> int:
        """Initialize default approval rules.

        Returns:
            Number of rules created
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        created = 0

        for rule_def in self.DEFAULT_RULES:
            key = rule_def["category"].value

            existing = await redis.hget(self.RULES_KEY, key)
            if existing:
                continue

            rule = ApprovalRule(
                id=str(uuid.uuid4())[:8],
                category=rule_def["category"],
                risk_level=rule_def["risk_level"],
                required_approvers=rule_def["required_approvers"],
                allowed_approvers=rule_def["allowed_approvers"],
                auto_expire_hours=rule_def["auto_expire_hours"],
                require_reason=rule_def["require_reason"],
                notify_on_request=rule_def["notify_on_request"],
                enabled=True,
            )

            await redis.hset(
                self.RULES_KEY,
                key,
                json.dumps(rule.to_dict()),
            )
            created += 1

        logger.info(f"[ApprovalGates] Initialized {created} default rules")
        return created

    async def get_rule(self, category: ActionCategory) -> ApprovalRule | None:
        """Get approval rule for category.

        Args:
            category: Action category

        Returns:
            Rule or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hget(self.RULES_KEY, category.value)
        if not raw:
            return None

        data = json.loads(raw)

        return ApprovalRule(
            id=data["id"],
            category=ActionCategory(data["category"]),
            risk_level=RiskLevel(data["risk_level"]),
            required_approvers=data["required_approvers"],
            allowed_approvers=data["allowed_approvers"],
            auto_expire_hours=data["auto_expire_hours"],
            require_reason=data["require_reason"],
            notify_on_request=data["notify_on_request"],
            enabled=data["enabled"],
        )

    async def list_rules(self) -> list[ApprovalRule]:
        """List all approval rules.

        Returns:
            List of rules
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hgetall(self.RULES_KEY)
        rules = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)
                rules.append(ApprovalRule(
                    id=data["id"],
                    category=ActionCategory(data["category"]),
                    risk_level=RiskLevel(data["risk_level"]),
                    required_approvers=data["required_approvers"],
                    allowed_approvers=data["allowed_approvers"],
                    auto_expire_hours=data["auto_expire_hours"],
                    require_reason=data["require_reason"],
                    notify_on_request=data["notify_on_request"],
                    enabled=data["enabled"],
                ))
            except Exception:
                continue

        return rules

    async def request_approval(
        self,
        action: str,
        category: ActionCategory,
        requester: str,
        reason: str = "",
        context: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        """Request approval for an action.

        Args:
            action: Description of action
            category: Action category
            requester: Who is requesting
            reason: Reason for action
            context: Additional context

        Returns:
            Approval request

        Raises:
            ValueError: If reason required but not provided
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get rule
        rule = await self.get_rule(category)
        if not rule:
            # Default rule for unknown categories
            rule = ApprovalRule(
                id="default",
                category=category,
                risk_level=RiskLevel.MEDIUM,
                required_approvers=1,
                allowed_approvers=["admin"],
                auto_expire_hours=24,
                require_reason=False,
                notify_on_request=False,
                enabled=True,
            )

        if rule.require_reason and not reason:
            raise ValueError("Reason is required for this action")

        request = ApprovalRequest(
            id=str(uuid.uuid4())[:8],
            action=action,
            category=category,
            risk_level=rule.risk_level,
            requester=requester,
            status=ApprovalStatus.PENDING,
            created_at=now,
            expires_at=now + timedelta(hours=rule.auto_expire_hours),
            required_approvers=rule.required_approvers,
            current_approvers=[],
            reason=reason,
            context=context or {},
        )

        await redis.hset(
            self.REQUESTS_KEY,
            request.id,
            json.dumps(request.to_dict()),
        )

        # Record in ops journal
        try:
            from app.services.ops_journal import ops_journal
            await ops_journal.record(
                action="approval_requested",
                actor=requester,
                details={
                    "request_id": request.id,
                    "action": action,
                    "category": category.value,
                    "risk_level": rule.risk_level.value,
                },
                severity="info",
            )
        except Exception:
            pass

        logger.info(f"[ApprovalGates] Request {request.id}: {action} by {requester}")

        return request

    async def approve(
        self,
        request_id: str,
        approver: str,
        approver_role: str = "",
        reason: str | None = None,
    ) -> ApprovalRequest | None:
        """Approve a request.

        Args:
            request_id: Request ID
            approver: Who is approving
            approver_role: Approver's role
            reason: Approval reason

        Returns:
            Updated request or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        request = await self.get_request(request_id)
        if not request:
            return None

        if request.status != ApprovalStatus.PENDING:
            return request

        # Check expiration
        if now >= request.expires_at:
            request.status = ApprovalStatus.EXPIRED
            await redis.hset(
                self.REQUESTS_KEY,
                request_id,
                json.dumps(request.to_dict()),
            )
            return request

        # Record decision
        decision = ApprovalDecision(
            request_id=request_id,
            approver=approver,
            decision="approve",
            reason=reason,
            decided_at=now,
        )

        await redis.lpush(
            f"{self.DECISIONS_KEY}:{request_id}",
            json.dumps(decision.to_dict()),
        )

        # Add approver
        if approver not in request.current_approvers:
            request.current_approvers.append(approver)

        # Check if fully approved
        if len(request.current_approvers) >= request.required_approvers:
            request.status = ApprovalStatus.APPROVED
            request.decision_at = now
            request.decision_by = approver

        await redis.hset(
            self.REQUESTS_KEY,
            request_id,
            json.dumps(request.to_dict()),
        )

        # Record in ops journal
        try:
            from app.services.ops_journal import ops_journal
            await ops_journal.record(
                action="approval_decision",
                actor=approver,
                details={
                    "request_id": request_id,
                    "decision": "approve",
                    "status": request.status.value,
                },
                severity="info",
            )
        except Exception:
            pass

        logger.info(f"[ApprovalGates] {request_id} approved by {approver}: {request.status.value}")

        return request

    async def reject(
        self,
        request_id: str,
        rejector: str,
        reason: str,
    ) -> ApprovalRequest | None:
        """Reject a request.

        Args:
            request_id: Request ID
            rejector: Who is rejecting
            reason: Rejection reason

        Returns:
            Updated request or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        request = await self.get_request(request_id)
        if not request:
            return None

        if request.status != ApprovalStatus.PENDING:
            return request

        # Record decision
        decision = ApprovalDecision(
            request_id=request_id,
            approver=rejector,
            decision="reject",
            reason=reason,
            decided_at=now,
        )

        await redis.lpush(
            f"{self.DECISIONS_KEY}:{request_id}",
            json.dumps(decision.to_dict()),
        )

        request.status = ApprovalStatus.REJECTED
        request.decision_at = now
        request.decision_by = rejector
        request.rejection_reason = reason

        await redis.hset(
            self.REQUESTS_KEY,
            request_id,
            json.dumps(request.to_dict()),
        )

        # Record in ops journal
        try:
            from app.services.ops_journal import ops_journal
            await ops_journal.record(
                action="approval_decision",
                actor=rejector,
                details={
                    "request_id": request_id,
                    "decision": "reject",
                    "reason": reason,
                },
                severity="warning",
            )
        except Exception:
            pass

        logger.info(f"[ApprovalGates] {request_id} rejected by {rejector}")

        return request

    async def get_request(self, request_id: str) -> ApprovalRequest | None:
        """Get approval request by ID.

        Args:
            request_id: Request ID

        Returns:
            Request or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hget(self.REQUESTS_KEY, request_id)
        if not raw:
            return None

        data = json.loads(raw)

        return ApprovalRequest(
            id=data["id"],
            action=data["action"],
            category=ActionCategory(data["category"]),
            risk_level=RiskLevel(data["risk_level"]),
            requester=data["requester"],
            status=ApprovalStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            required_approvers=data["required_approvers"],
            current_approvers=data["current_approvers"],
            reason=data["reason"],
            context=data["context"],
            decision_at=datetime.fromisoformat(data["decision_at"]) if data.get("decision_at") else None,
            decision_by=data.get("decision_by"),
            rejection_reason=data.get("rejection_reason"),
        )

    async def list_pending(
        self,
        category: ActionCategory | None = None,
    ) -> list[ApprovalRequest]:
        """List pending requests.

        Args:
            category: Filter by category

        Returns:
            List of pending requests
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        raw = await redis.hgetall(self.REQUESTS_KEY)
        requests = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)

                if data["status"] != ApprovalStatus.PENDING.value:
                    continue

                if category and data["category"] != category.value:
                    continue

                # Check expiration
                expires = datetime.fromisoformat(data["expires_at"])
                if now >= expires:
                    continue

                requests.append(ApprovalRequest(
                    id=data["id"],
                    action=data["action"],
                    category=ActionCategory(data["category"]),
                    risk_level=RiskLevel(data["risk_level"]),
                    requester=data["requester"],
                    status=ApprovalStatus(data["status"]),
                    created_at=datetime.fromisoformat(data["created_at"]),
                    expires_at=expires,
                    required_approvers=data["required_approvers"],
                    current_approvers=data["current_approvers"],
                    reason=data["reason"],
                    context=data["context"],
                ))
            except Exception:
                continue

        # Sort by created_at (oldest first)
        requests.sort(key=lambda r: r.created_at)
        return requests

    async def check_approval(
        self,
        request_id: str,
    ) -> tuple[bool, str]:
        """Check if action is approved.

        Args:
            request_id: Request ID

        Returns:
            (approved, status_message) tuple
        """
        request = await self.get_request(request_id)

        if not request:
            return False, "Request not found"

        if request.status == ApprovalStatus.APPROVED:
            return True, "Approved"
        elif request.status == ApprovalStatus.REJECTED:
            return False, f"Rejected: {request.rejection_reason}"
        elif request.status == ApprovalStatus.EXPIRED:
            return False, "Request expired"
        elif request.status == ApprovalStatus.PENDING:
            approvers = len(request.current_approvers)
            required = request.required_approvers
            return False, f"Pending approval ({approvers}/{required})"
        else:
            return False, f"Status: {request.status.value}"

    async def cancel(
        self,
        request_id: str,
        cancelled_by: str,
    ) -> ApprovalRequest | None:
        """Cancel an approval request.

        Args:
            request_id: Request ID
            cancelled_by: Who cancelled

        Returns:
            Updated request or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        request = await self.get_request(request_id)
        if not request:
            return None

        if request.status != ApprovalStatus.PENDING:
            return request

        request.status = ApprovalStatus.CANCELLED
        request.decision_at = datetime.now(UTC)
        request.decision_by = cancelled_by

        await redis.hset(
            self.REQUESTS_KEY,
            request_id,
            json.dumps(request.to_dict()),
        )

        logger.info(f"[ApprovalGates] {request_id} cancelled by {cancelled_by}")

        return request


# Singleton
approval_gates = ApprovalGatesService()
