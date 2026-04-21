"""Incident Timeline Service.

Incident tracking and timeline management.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
import uuid

UTC = timezone.utc

logger = logging.getLogger(__name__)


class IncidentSeverity(str, Enum):
    """Incident severity levels."""

    SEV1 = "sev1"  # Critical - full outage
    SEV2 = "sev2"  # Major - significant impact
    SEV3 = "sev3"  # Minor - limited impact
    SEV4 = "sev4"  # Low - minimal impact


class IncidentStatus(str, Enum):
    """Incident status."""

    DETECTED = "detected"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    POSTMORTEM = "postmortem"
    CLOSED = "closed"


class TimelineEventType(str, Enum):
    """Timeline event types."""

    CREATED = "created"
    STATUS_CHANGE = "status_change"
    SEVERITY_CHANGE = "severity_change"
    ASSIGNEE_CHANGE = "assignee_change"
    COMMENT = "comment"
    ACTION = "action"
    ALERT = "alert"
    METRIC = "metric"
    RESOLVED = "resolved"


@dataclass
class TimelineEvent:
    """Timeline event."""

    id: str
    event_type: TimelineEventType
    timestamp: datetime
    actor: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "content": self.content,
            "metadata": self.metadata,
        }


@dataclass
class Incident:
    """Incident record."""

    id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus
    created_at: datetime
    created_by: str
    assignee: str | None
    affected_services: list[str]
    timeline: list[TimelineEvent]
    resolved_at: datetime | None = None
    resolution_summary: str | None = None
    postmortem_url: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "assignee": self.assignee,
            "affected_services": self.affected_services,
            "timeline": [e.to_dict() for e in self.timeline],
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_summary": self.resolution_summary,
            "postmortem_url": self.postmortem_url,
            "tags": self.tags,
            "metadata": self.metadata,
            "duration_minutes": self._calculate_duration(),
            "mttr_minutes": self._calculate_mttr(),
        }

    def _calculate_duration(self) -> float | None:
        """Calculate incident duration."""
        if self.resolved_at:
            return (self.resolved_at - self.created_at).total_seconds() / 60
        return (datetime.now(UTC) - self.created_at).total_seconds() / 60

    def _calculate_mttr(self) -> float | None:
        """Calculate mean time to resolve."""
        if self.resolved_at:
            return (self.resolved_at - self.created_at).total_seconds() / 60
        return None


@dataclass
class IncidentStats:
    """Incident statistics."""

    period_days: int
    total_incidents: int
    by_severity: dict[str, int]
    by_status: dict[str, int]
    avg_resolution_minutes: float
    mttr_by_severity: dict[str, float]
    incidents_per_day: float
    top_affected_services: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "period_days": self.period_days,
            "total_incidents": self.total_incidents,
            "by_severity": self.by_severity,
            "by_status": self.by_status,
            "avg_resolution_minutes": round(self.avg_resolution_minutes, 1),
            "mttr_by_severity": {k: round(v, 1) for k, v in self.mttr_by_severity.items()},
            "incidents_per_day": round(self.incidents_per_day, 2),
            "top_affected_services": self.top_affected_services,
        }


class IncidentTimelineService:
    """Service for incident tracking and timeline.

    Features:
    - Incident creation and management
    - Timeline tracking
    - Status transitions
    - Resolution tracking
    - MTTR calculation
    """

    INCIDENTS_KEY = "incidents:all"
    ACTIVE_KEY = "incidents:active"
    STATS_KEY = "incidents:stats"

    def __init__(self) -> None:
        """Initialize service."""
        pass

    async def create_incident(
        self,
        title: str,
        description: str,
        severity: IncidentSeverity,
        created_by: str,
        affected_services: list[str] | None = None,
        assignee: str | None = None,
        tags: list[str] | None = None,
    ) -> Incident:
        """Create a new incident.

        Args:
            title: Incident title
            description: Incident description
            severity: Severity level
            created_by: Who created it
            affected_services: Affected services
            assignee: Initial assignee
            tags: Tags

        Returns:
            Created incident
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        incident_id = str(uuid.uuid4())[:8]

        # Create initial timeline event
        timeline_event = TimelineEvent(
            id=str(uuid.uuid4()),
            event_type=TimelineEventType.CREATED,
            timestamp=now,
            actor=created_by,
            content=f"Incident created: {title}",
            metadata={"severity": severity.value},
        )

        incident = Incident(
            id=incident_id,
            title=title,
            description=description,
            severity=severity,
            status=IncidentStatus.DETECTED,
            created_at=now,
            created_by=created_by,
            assignee=assignee,
            affected_services=affected_services or [],
            timeline=[timeline_event],
            tags=tags or [],
        )

        # Store incident
        await redis.hset(
            self.INCIDENTS_KEY,
            incident.id,
            json.dumps(incident.to_dict()),
        )

        # Add to active incidents
        await redis.sadd(self.ACTIVE_KEY, incident.id)

        # Record in ops journal
        try:
            from app.services.ops_journal import ops_journal
            await ops_journal.record(
                action="incident_created",
                actor=created_by,
                details={
                    "incident_id": incident.id,
                    "title": title,
                    "severity": severity.value,
                },
                severity="critical" if severity in [IncidentSeverity.SEV1, IncidentSeverity.SEV2] else "warning",
            )
        except Exception:
            pass

        logger.warning(
            f"[Incident] Created: {incident.id} - {title} ({severity.value})"
        )

        return incident

    async def get_incident(self, incident_id: str) -> Incident | None:
        """Get incident by ID.

        Args:
            incident_id: Incident ID

        Returns:
            Incident if found
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        data = await redis.hget(self.INCIDENTS_KEY, incident_id)

        if not data:
            return None

        return self._parse_incident(json.loads(data))

    def _parse_incident(self, data: dict[str, Any]) -> Incident:
        """Parse incident from dict."""
        return Incident(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            severity=IncidentSeverity(data["severity"]),
            status=IncidentStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            created_by=data["created_by"],
            assignee=data.get("assignee"),
            affected_services=data.get("affected_services", []),
            timeline=[
                TimelineEvent(
                    id=e["id"],
                    event_type=TimelineEventType(e["event_type"]),
                    timestamp=datetime.fromisoformat(e["timestamp"]),
                    actor=e["actor"],
                    content=e["content"],
                    metadata=e.get("metadata", {}),
                )
                for e in data.get("timeline", [])
            ],
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            resolution_summary=data.get("resolution_summary"),
            postmortem_url=data.get("postmortem_url"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )

    async def add_timeline_event(
        self,
        incident_id: str,
        event_type: TimelineEventType,
        actor: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Incident | None:
        """Add event to incident timeline.

        Args:
            incident_id: Incident ID
            event_type: Event type
            actor: Who performed action
            content: Event content
            metadata: Additional data

        Returns:
            Updated incident
        """
        incident = await self.get_incident(incident_id)
        if not incident:
            return None

        event = TimelineEvent(
            id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.now(UTC),
            actor=actor,
            content=content,
            metadata=metadata or {},
        )

        incident.timeline.append(event)

        await self._save_incident(incident)

        return incident

    async def update_status(
        self,
        incident_id: str,
        new_status: IncidentStatus,
        actor: str,
        comment: str | None = None,
    ) -> Incident | None:
        """Update incident status.

        Args:
            incident_id: Incident ID
            new_status: New status
            actor: Who changed status
            comment: Optional comment

        Returns:
            Updated incident
        """
        from app.storage.redis import get_redis

        incident = await self.get_incident(incident_id)
        if not incident:
            return None

        old_status = incident.status
        incident.status = new_status

        # Add timeline event
        content = f"Status changed: {old_status.value} → {new_status.value}"
        if comment:
            content += f" - {comment}"

        event = TimelineEvent(
            id=str(uuid.uuid4()),
            event_type=TimelineEventType.STATUS_CHANGE,
            timestamp=datetime.now(UTC),
            actor=actor,
            content=content,
            metadata={"old_status": old_status.value, "new_status": new_status.value},
        )
        incident.timeline.append(event)

        # Handle resolution
        if new_status == IncidentStatus.RESOLVED:
            incident.resolved_at = datetime.now(UTC)

            redis = await get_redis()
            await redis.srem(self.ACTIVE_KEY, incident_id)

            # Add resolved event
            resolved_event = TimelineEvent(
                id=str(uuid.uuid4()),
                event_type=TimelineEventType.RESOLVED,
                timestamp=incident.resolved_at,
                actor=actor,
                content="Incident resolved",
            )
            incident.timeline.append(resolved_event)

        await self._save_incident(incident)

        logger.info(
            f"[Incident] {incident_id} status: {old_status.value} -> {new_status.value}"
        )

        return incident

    async def update_severity(
        self,
        incident_id: str,
        new_severity: IncidentSeverity,
        actor: str,
        reason: str,
    ) -> Incident | None:
        """Update incident severity.

        Args:
            incident_id: Incident ID
            new_severity: New severity
            actor: Who changed severity
            reason: Reason for change

        Returns:
            Updated incident
        """
        incident = await self.get_incident(incident_id)
        if not incident:
            return None

        old_severity = incident.severity
        incident.severity = new_severity

        event = TimelineEvent(
            id=str(uuid.uuid4()),
            event_type=TimelineEventType.SEVERITY_CHANGE,
            timestamp=datetime.now(UTC),
            actor=actor,
            content=f"Severity changed: {old_severity.value} → {new_severity.value}. {reason}",
            metadata={"old_severity": old_severity.value, "new_severity": new_severity.value},
        )
        incident.timeline.append(event)

        await self._save_incident(incident)

        return incident

    async def assign_incident(
        self,
        incident_id: str,
        assignee: str,
        actor: str,
    ) -> Incident | None:
        """Assign incident to someone.

        Args:
            incident_id: Incident ID
            assignee: New assignee
            actor: Who assigned

        Returns:
            Updated incident
        """
        incident = await self.get_incident(incident_id)
        if not incident:
            return None

        old_assignee = incident.assignee
        incident.assignee = assignee

        event = TimelineEvent(
            id=str(uuid.uuid4()),
            event_type=TimelineEventType.ASSIGNEE_CHANGE,
            timestamp=datetime.now(UTC),
            actor=actor,
            content=f"Assigned to {assignee}" + (f" (from {old_assignee})" if old_assignee else ""),
            metadata={"old_assignee": old_assignee, "new_assignee": assignee},
        )
        incident.timeline.append(event)

        await self._save_incident(incident)

        return incident

    async def resolve_incident(
        self,
        incident_id: str,
        actor: str,
        resolution_summary: str,
    ) -> Incident | None:
        """Resolve an incident.

        Args:
            incident_id: Incident ID
            actor: Who resolved
            resolution_summary: Summary of resolution

        Returns:
            Updated incident
        """
        incident = await self.update_status(
            incident_id=incident_id,
            new_status=IncidentStatus.RESOLVED,
            actor=actor,
            comment=resolution_summary,
        )

        if incident:
            incident.resolution_summary = resolution_summary
            await self._save_incident(incident)

        return incident

    async def _save_incident(self, incident: Incident) -> None:
        """Save incident to storage."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        await redis.hset(
            self.INCIDENTS_KEY,
            incident.id,
            json.dumps(incident.to_dict()),
        )

    async def list_incidents(
        self,
        status: IncidentStatus | None = None,
        severity: IncidentSeverity | None = None,
        active_only: bool = False,
        limit: int = 50,
    ) -> list[Incident]:
        """List incidents.

        Args:
            status: Filter by status
            severity: Filter by severity
            active_only: Only active incidents
            limit: Max results

        Returns:
            List of incidents
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        if active_only:
            active_ids = await redis.smembers(self.ACTIVE_KEY)
            incidents = []
            for iid in active_ids:
                data = await redis.hget(self.INCIDENTS_KEY, iid)
                if data:
                    incidents.append(self._parse_incident(json.loads(data)))
        else:
            all_data = await redis.hgetall(self.INCIDENTS_KEY)
            incidents = [
                self._parse_incident(json.loads(data))
                for data in all_data.values()
            ]

        # Apply filters
        if status:
            incidents = [i for i in incidents if i.status == status]
        if severity:
            incidents = [i for i in incidents if i.severity == severity]

        # Sort by created_at descending
        incidents.sort(key=lambda i: i.created_at, reverse=True)

        return incidents[:limit]

    async def get_active_incidents(self) -> list[Incident]:
        """Get all active incidents.

        Returns:
            Active incidents
        """
        return await self.list_incidents(active_only=True)

    async def get_stats(
        self,
        days: int = 30,
    ) -> IncidentStats:
        """Get incident statistics.

        Args:
            days: Period in days

        Returns:
            Incident stats
        """
        incidents = await self.list_incidents(limit=1000)
        cutoff = datetime.now(UTC) - timedelta(days=days)

        # Filter to period
        period_incidents = [i for i in incidents if i.created_at >= cutoff]

        # Calculate stats
        by_severity: dict[str, int] = {}
        by_status: dict[str, int] = {}
        resolution_times: list[float] = []
        mttr_by_sev: dict[str, list[float]] = {}
        service_counts: dict[str, int] = {}

        for inc in period_incidents:
            # By severity
            by_severity[inc.severity.value] = by_severity.get(inc.severity.value, 0) + 1

            # By status
            by_status[inc.status.value] = by_status.get(inc.status.value, 0) + 1

            # Resolution time
            if inc.resolved_at:
                resolution_min = (inc.resolved_at - inc.created_at).total_seconds() / 60
                resolution_times.append(resolution_min)

                if inc.severity.value not in mttr_by_sev:
                    mttr_by_sev[inc.severity.value] = []
                mttr_by_sev[inc.severity.value].append(resolution_min)

            # Services
            for service in inc.affected_services:
                service_counts[service] = service_counts.get(service, 0) + 1

        avg_resolution = (
            sum(resolution_times) / len(resolution_times)
            if resolution_times
            else 0
        )

        mttr_avg = {
            sev: sum(times) / len(times)
            for sev, times in mttr_by_sev.items()
        }

        top_services = sorted(
            [{"service": s, "count": c} for s, c in service_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:10]

        return IncidentStats(
            period_days=days,
            total_incidents=len(period_incidents),
            by_severity=by_severity,
            by_status=by_status,
            avg_resolution_minutes=avg_resolution,
            mttr_by_severity=mttr_avg,
            incidents_per_day=len(period_incidents) / days if days > 0 else 0,
            top_affected_services=top_services,
        )


# Singleton
incident_timeline = IncidentTimelineService()
