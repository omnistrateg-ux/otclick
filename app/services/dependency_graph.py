"""Dependency Graph Service.

Service/component dependency mapping and analysis.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

UTC = timezone.utc

logger = logging.getLogger(__name__)


class NodeType(str, Enum):
    """Types of dependency graph nodes."""

    SERVICE = "service"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    EXTERNAL_API = "external_api"
    STORAGE = "storage"
    CONFIG = "config"


class DependencyType(str, Enum):
    """Type of dependency relationship."""

    REQUIRED = "required"  # Hard dependency, must be available
    OPTIONAL = "optional"  # Soft dependency, can work without
    ASYNC = "async"  # Async dependency (queue-based)
    FALLBACK = "fallback"  # Used as fallback


class HealthStatus(str, Enum):
    """Health status of a node."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class DependencyNode:
    """Node in dependency graph."""

    id: str
    name: str
    node_type: NodeType
    version: str | None
    health: HealthStatus
    metadata: dict[str, Any]
    last_health_check: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "node_type": self.node_type.value,
            "version": self.version,
            "health": self.health.value,
            "metadata": self.metadata,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
        }


@dataclass
class DependencyEdge:
    """Edge representing dependency relationship."""

    id: str
    source_id: str
    target_id: str
    dependency_type: DependencyType
    description: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "dependency_type": self.dependency_type.value,
            "description": self.description,
            "metadata": self.metadata,
        }


@dataclass
class ImpactAnalysis:
    """Impact analysis result for a node failure."""

    failed_node_id: str
    failed_node_name: str
    directly_affected: list[str]
    transitively_affected: list[str]
    severity: str
    mitigation_options: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "failed_node_id": self.failed_node_id,
            "failed_node_name": self.failed_node_name,
            "directly_affected": self.directly_affected,
            "transitively_affected": self.transitively_affected,
            "severity": self.severity,
            "mitigation_options": self.mitigation_options,
        }


class DependencyGraphService:
    """Service for dependency graph management.

    Features:
    - Register nodes and dependencies
    - Visualize dependency relationships
    - Impact analysis
    - Health propagation
    """

    NODES_KEY = "depgraph:nodes"
    EDGES_KEY = "depgraph:edges"

    # Default system topology
    DEFAULT_NODES = [
        {
            "name": "api",
            "node_type": NodeType.SERVICE,
            "version": "1.0.0",
            "metadata": {"port": 8000, "replicas": 2},
        },
        {
            "name": "postgres",
            "node_type": NodeType.DATABASE,
            "version": "15",
            "metadata": {"host": "localhost", "port": 5432},
        },
        {
            "name": "redis",
            "node_type": NodeType.CACHE,
            "version": "7",
            "metadata": {"host": "localhost", "port": 6379},
        },
        {
            "name": "celery",
            "node_type": NodeType.QUEUE,
            "version": "5.3",
            "metadata": {"workers": 4},
        },
        {
            "name": "openai",
            "node_type": NodeType.EXTERNAL_API,
            "version": None,
            "metadata": {"provider": "openai"},
        },
        {
            "name": "anthropic",
            "node_type": NodeType.EXTERNAL_API,
            "version": None,
            "metadata": {"provider": "anthropic"},
        },
        {
            "name": "smtp",
            "node_type": NodeType.EXTERNAL_API,
            "version": None,
            "metadata": {"provider": "sendgrid"},
        },
    ]

    DEFAULT_EDGES = [
        {"source": "api", "target": "postgres", "type": DependencyType.REQUIRED, "desc": "Data storage"},
        {"source": "api", "target": "redis", "type": DependencyType.REQUIRED, "desc": "Caching and state"},
        {"source": "api", "target": "celery", "type": DependencyType.OPTIONAL, "desc": "Async tasks"},
        {"source": "celery", "target": "redis", "type": DependencyType.REQUIRED, "desc": "Task broker"},
        {"source": "celery", "target": "postgres", "type": DependencyType.REQUIRED, "desc": "Task results"},
        {"source": "celery", "target": "openai", "type": DependencyType.OPTIONAL, "desc": "LLM provider"},
        {"source": "celery", "target": "anthropic", "type": DependencyType.FALLBACK, "desc": "LLM fallback"},
        {"source": "celery", "target": "smtp", "type": DependencyType.OPTIONAL, "desc": "Email sending"},
    ]

    def __init__(self) -> None:
        """Initialize service."""
        self._nodes_cache: dict[str, DependencyNode] = {}
        self._edges_cache: dict[str, DependencyEdge] = {}

    async def initialize_defaults(self) -> tuple[int, int]:
        """Initialize default topology.

        Returns:
            (nodes_created, edges_created)
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        nodes_created = 0
        edges_created = 0

        # Create nodes
        for node_def in self.DEFAULT_NODES:
            existing = await redis.hget(self.NODES_KEY, node_def["name"])
            if existing:
                continue

            node = DependencyNode(
                id=str(uuid.uuid4())[:8],
                name=node_def["name"],
                node_type=node_def["node_type"],
                version=node_def.get("version"),
                health=HealthStatus.UNKNOWN,
                metadata=node_def.get("metadata", {}),
                last_health_check=None,
            )

            await redis.hset(
                self.NODES_KEY,
                node.name,
                json.dumps(node.to_dict()),
            )
            nodes_created += 1

        # Create edges
        for edge_def in self.DEFAULT_EDGES:
            edge_key = f"{edge_def['source']}:{edge_def['target']}"
            existing = await redis.hget(self.EDGES_KEY, edge_key)
            if existing:
                continue

            edge = DependencyEdge(
                id=str(uuid.uuid4())[:8],
                source_id=edge_def["source"],
                target_id=edge_def["target"],
                dependency_type=edge_def["type"],
                description=edge_def["desc"],
                metadata={},
            )

            await redis.hset(
                self.EDGES_KEY,
                edge_key,
                json.dumps(edge.to_dict()),
            )
            edges_created += 1

        logger.info(f"[DependencyGraph] Initialized {nodes_created} nodes, {edges_created} edges")
        return nodes_created, edges_created

    async def register_node(
        self,
        name: str,
        node_type: NodeType,
        version: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DependencyNode:
        """Register a dependency node.

        Args:
            name: Node name
            node_type: Type of node
            version: Version string
            metadata: Additional metadata

        Returns:
            Created node
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        node = DependencyNode(
            id=str(uuid.uuid4())[:8],
            name=name,
            node_type=node_type,
            version=version,
            health=HealthStatus.UNKNOWN,
            metadata=metadata or {},
        )

        await redis.hset(
            self.NODES_KEY,
            name,
            json.dumps(node.to_dict()),
        )

        logger.info(f"[DependencyGraph] Registered node: {name}")
        return node

    async def add_dependency(
        self,
        source: str,
        target: str,
        dependency_type: DependencyType = DependencyType.REQUIRED,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> DependencyEdge:
        """Add dependency relationship.

        Args:
            source: Source node name
            target: Target node name
            dependency_type: Type of dependency
            description: Description
            metadata: Additional metadata

        Returns:
            Created edge
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        edge = DependencyEdge(
            id=str(uuid.uuid4())[:8],
            source_id=source,
            target_id=target,
            dependency_type=dependency_type,
            description=description,
            metadata=metadata or {},
        )

        edge_key = f"{source}:{target}"
        await redis.hset(
            self.EDGES_KEY,
            edge_key,
            json.dumps(edge.to_dict()),
        )

        logger.info(f"[DependencyGraph] Added dependency: {source} -> {target}")
        return edge

    async def get_node(self, name: str) -> DependencyNode | None:
        """Get node by name.

        Args:
            name: Node name

        Returns:
            Node or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hget(self.NODES_KEY, name)
        if not raw:
            return None

        data = json.loads(raw)

        return DependencyNode(
            id=data["id"],
            name=data["name"],
            node_type=NodeType(data["node_type"]),
            version=data.get("version"),
            health=HealthStatus(data["health"]),
            metadata=data.get("metadata", {}),
            last_health_check=datetime.fromisoformat(data["last_health_check"]) if data.get("last_health_check") else None,
        )

    async def update_health(
        self,
        name: str,
        health: HealthStatus,
    ) -> DependencyNode | None:
        """Update node health status.

        Args:
            name: Node name
            health: New health status

        Returns:
            Updated node or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        node = await self.get_node(name)
        if not node:
            return None

        node.health = health
        node.last_health_check = datetime.now(UTC)

        await redis.hset(
            self.NODES_KEY,
            name,
            json.dumps(node.to_dict()),
        )

        return node

    async def get_all_nodes(self) -> list[DependencyNode]:
        """Get all nodes.

        Returns:
            List of nodes
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hgetall(self.NODES_KEY)
        nodes = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)
                nodes.append(DependencyNode(
                    id=data["id"],
                    name=data["name"],
                    node_type=NodeType(data["node_type"]),
                    version=data.get("version"),
                    health=HealthStatus(data["health"]),
                    metadata=data.get("metadata", {}),
                    last_health_check=datetime.fromisoformat(data["last_health_check"]) if data.get("last_health_check") else None,
                ))
            except Exception:
                continue

        return nodes

    async def get_all_edges(self) -> list[DependencyEdge]:
        """Get all edges.

        Returns:
            List of edges
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hgetall(self.EDGES_KEY)
        edges = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)
                edges.append(DependencyEdge(
                    id=data["id"],
                    source_id=data["source_id"],
                    target_id=data["target_id"],
                    dependency_type=DependencyType(data["dependency_type"]),
                    description=data.get("description", ""),
                    metadata=data.get("metadata", {}),
                ))
            except Exception:
                continue

        return edges

    async def get_dependencies(self, name: str) -> list[DependencyEdge]:
        """Get dependencies of a node.

        Args:
            name: Node name

        Returns:
            List of outgoing edges
        """
        edges = await self.get_all_edges()
        return [e for e in edges if e.source_id == name]

    async def get_dependents(self, name: str) -> list[DependencyEdge]:
        """Get nodes that depend on this node.

        Args:
            name: Node name

        Returns:
            List of incoming edges
        """
        edges = await self.get_all_edges()
        return [e for e in edges if e.target_id == name]

    async def analyze_impact(
        self,
        node_name: str,
    ) -> ImpactAnalysis:
        """Analyze impact of node failure.

        Args:
            node_name: Name of failing node

        Returns:
            Impact analysis
        """
        node = await self.get_node(node_name)
        if not node:
            return ImpactAnalysis(
                failed_node_id="",
                failed_node_name=node_name,
                directly_affected=[],
                transitively_affected=[],
                severity="unknown",
                mitigation_options=["Node not found in graph"],
            )

        edges = await self.get_all_edges()

        # Find directly affected (nodes that require this one)
        directly_affected = []
        for edge in edges:
            if edge.target_id == node_name and edge.dependency_type == DependencyType.REQUIRED:
                directly_affected.append(edge.source_id)

        # Find transitively affected (BFS)
        transitively_affected = []
        queue = list(directly_affected)
        visited = set(directly_affected)

        while queue:
            current = queue.pop(0)
            for edge in edges:
                if edge.target_id == current and edge.dependency_type == DependencyType.REQUIRED:
                    if edge.source_id not in visited:
                        visited.add(edge.source_id)
                        transitively_affected.append(edge.source_id)
                        queue.append(edge.source_id)

        # Determine severity
        total_affected = len(directly_affected) + len(transitively_affected)
        if node.node_type in [NodeType.DATABASE, NodeType.CACHE]:
            severity = "critical"
        elif total_affected >= 3:
            severity = "high"
        elif total_affected >= 1:
            severity = "medium"
        else:
            severity = "low"

        # Mitigation options
        mitigations = []
        if node.node_type == NodeType.DATABASE:
            mitigations.append("Failover to replica")
            mitigations.append("Enable read-only mode")
        elif node.node_type == NodeType.CACHE:
            mitigations.append("Clear and rebuild cache")
            mitigations.append("Switch to database-direct mode")
        elif node.node_type == NodeType.EXTERNAL_API:
            mitigations.append("Switch to fallback provider")
            mitigations.append("Enable circuit breaker")
        else:
            mitigations.append("Restart service")
            mitigations.append("Scale horizontal replicas")

        return ImpactAnalysis(
            failed_node_id=node.id,
            failed_node_name=node_name,
            directly_affected=directly_affected,
            transitively_affected=transitively_affected,
            severity=severity,
            mitigation_options=mitigations,
        )

    async def get_graph(self) -> dict[str, Any]:
        """Get full dependency graph.

        Returns:
            Graph data with nodes and edges
        """
        nodes = await self.get_all_nodes()
        edges = await self.get_all_edges()

        return {
            "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges],
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    async def get_critical_path(self) -> list[str]:
        """Get critical path (nodes with most dependents).

        Returns:
            List of critical node names
        """
        edges = await self.get_all_edges()

        # Count incoming edges (dependents)
        dependent_count: dict[str, int] = {}
        for edge in edges:
            if edge.dependency_type == DependencyType.REQUIRED:
                dependent_count[edge.target_id] = dependent_count.get(edge.target_id, 0) + 1

        # Sort by count
        sorted_nodes = sorted(
            dependent_count.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        return [name for name, _ in sorted_nodes]

    async def check_health_propagation(self) -> dict[str, HealthStatus]:
        """Check health with dependency propagation.

        A node is unhealthy if any required dependency is unhealthy.

        Returns:
            Map of node names to effective health
        """
        nodes = await self.get_all_nodes()
        edges = await self.get_all_edges()

        node_health = {n.name: n.health for n in nodes}
        effective_health: dict[str, HealthStatus] = {}

        # Topological sort would be ideal, but for simplicity iterate
        for _ in range(len(nodes)):
            changed = False
            for node in nodes:
                current = effective_health.get(node.name, node.health)

                # Check required dependencies
                deps = [e for e in edges if e.source_id == node.name and e.dependency_type == DependencyType.REQUIRED]

                for dep in deps:
                    dep_health = effective_health.get(dep.target_id, node_health.get(dep.target_id, HealthStatus.UNKNOWN))
                    if dep_health == HealthStatus.UNHEALTHY:
                        if current != HealthStatus.UNHEALTHY:
                            effective_health[node.name] = HealthStatus.UNHEALTHY
                            changed = True
                            break
                    elif dep_health == HealthStatus.DEGRADED:
                        if current == HealthStatus.HEALTHY:
                            effective_health[node.name] = HealthStatus.DEGRADED
                            changed = True

                if node.name not in effective_health:
                    effective_health[node.name] = current

            if not changed:
                break

        return effective_health


# Singleton
dependency_graph = DependencyGraphService()
