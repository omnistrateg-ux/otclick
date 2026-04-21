"""Dependency graph API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.dependency_graph import (
    DependencyGraphService,
    NodeType,
    DependencyType,
    HealthStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dependencies", tags=["dependencies"])


# Request models
class RegisterNodeRequest(BaseModel):
    """Register dependency node request."""

    name: str
    node_type: str
    version: str | None = None
    metadata: dict[str, Any] | None = None


class AddDependencyRequest(BaseModel):
    """Add dependency request."""

    source: str
    target: str
    dependency_type: str = "required"
    description: str = ""


class UpdateNodeHealthRequest(BaseModel):
    """Update node health request."""

    health: str


# Endpoints
@router.get("/graph")
async def get_dependency_graph() -> dict[str, Any]:
    """Get full dependency graph."""
    service = DependencyGraphService()
    return await service.get_graph()


@router.get("/nodes")
async def list_dependency_nodes() -> list[dict[str, Any]]:
    """List all nodes."""
    service = DependencyGraphService()
    nodes = await service.get_all_nodes()
    return [n.to_dict() for n in nodes]


@router.post("/nodes")
async def register_node(
    request: RegisterNodeRequest,
) -> dict[str, Any]:
    """Register dependency node."""
    service = DependencyGraphService()

    try:
        node_type = NodeType(request.node_type)
    except ValueError:
        valid = [t.value for t in NodeType]
        raise HTTPException(400, f"Invalid node type. Valid: {valid}")

    node = await service.register_node(
        name=request.name,
        node_type=node_type,
        version=request.version,
        metadata=request.metadata,
    )
    return node.to_dict()


@router.get("/nodes/{name}")
async def get_dependency_node(name: str) -> dict[str, Any]:
    """Get node by name."""
    service = DependencyGraphService()
    node = await service.get_node(name)
    if not node:
        raise HTTPException(404, "Node not found")
    return node.to_dict()


@router.put("/nodes/{name}/health")
async def update_node_health(
    name: str,
    request: UpdateNodeHealthRequest,
) -> dict[str, Any]:
    """Update node health."""
    service = DependencyGraphService()

    try:
        health = HealthStatus(request.health)
    except ValueError:
        valid = [h.value for h in HealthStatus]
        raise HTTPException(400, f"Invalid health. Valid: {valid}")

    node = await service.update_health(name, health)
    if not node:
        raise HTTPException(404, "Node not found")
    return node.to_dict()


@router.post("/edges")
async def add_dependency(
    request: AddDependencyRequest,
) -> dict[str, Any]:
    """Add dependency edge."""
    service = DependencyGraphService()

    try:
        dep_type = DependencyType(request.dependency_type)
    except ValueError:
        valid = [t.value for t in DependencyType]
        raise HTTPException(400, f"Invalid dependency type. Valid: {valid}")

    edge = await service.add_dependency(
        source=request.source,
        target=request.target,
        dependency_type=dep_type,
        description=request.description,
    )
    return edge.to_dict()


@router.get("/nodes/{name}/impact")
async def analyze_node_impact(name: str) -> dict[str, Any]:
    """Analyze impact of node failure."""
    service = DependencyGraphService()
    impact = await service.analyze_impact(name)
    return impact.to_dict()


@router.get("/critical-path")
async def get_critical_path() -> list[str]:
    """Get critical path nodes."""
    service = DependencyGraphService()
    return await service.get_critical_path()


@router.get("/health")
async def check_health_propagation() -> dict[str, str]:
    """Check health with propagation."""
    service = DependencyGraphService()
    return await service.check_health_propagation()


@router.post("/initialize")
async def initialize_dependency_graph() -> dict[str, Any]:
    """Initialize default topology."""
    service = DependencyGraphService()
    nodes, edges = await service.initialize_defaults()
    return {"nodes_created": nodes, "edges_created": edges}


# Reference endpoints
@router.get("/reference/node-types")
async def list_node_types() -> list[str]:
    """List available node types."""
    return [t.value for t in NodeType]


@router.get("/reference/dependency-types")
async def list_dependency_types() -> list[str]:
    """List available dependency types."""
    return [t.value for t in DependencyType]


@router.get("/reference/health-statuses")
async def list_health_statuses() -> list[str]:
    """List available health statuses."""
    return [h.value for h in HealthStatus]
