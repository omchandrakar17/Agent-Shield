"""Agent registry."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth import OperatorContext, OperatorDep
from app.core.http import api_error, get_request_id
from app.database import get_db
from app.models import AgentModel
from app.registry import ensure_registry, get_agent
from app.schemas.requests import AgentCreateRequest, AgentKillSwitchRequest
from app.security import now
from app.services.audit_service import record_audit
from app.services.incident_service import create_incident
from app.tenant import assert_org_resource, org_filter

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.get("")
def list_agents(db: Session = Depends(get_db), operator: OperatorContext = OperatorDep) -> list[dict]:
    ensure_registry(db)
    agents = org_filter(db.query(AgentModel), AgentModel, operator).all()
    return [{
        "id": a.id, "name": a.name, "owner": a.owner, "version": a.version,
        "status": a.status, "allowed_tools": a.allowed_tools, "model_provider": a.model_provider,
        "policy_id": a.policy_id,
        "limits": a.limits, "last_seen": a.last_seen, "created_at": a.created_at, "updated_at": a.updated_at,
    } for a in agents]


@router.post("")
def create_agent(
    body: AgentCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    operator: OperatorContext = OperatorDep,
) -> dict:
    req_id = get_request_id(request)
    if db.query(AgentModel).filter(AgentModel.id == body.id).first():
        raise api_error("AGENT_EXISTS", f"Agent '{body.id}' already exists", req_id, 409)
    agent = AgentModel(
        id=body.id, organization_id=operator.organization_id, name=body.name, owner=body.owner,
        version=body.version, status="ACTIVE", allowed_tools=body.allowed_tools, policy_id=body.policy_id,
        limits={"max_tool_calls": 12, "max_execution_seconds": 45},
        last_seen=None, created_at=now(), updated_at=now(),
    )
    db.add(agent)
    db.commit()
    return {"id": agent.id, "name": agent.name, "status": agent.status}


@router.get("/{agent_id}")
def get_agent_detail(
    agent_id: str,
    request: Request,
    db: Session = Depends(get_db),
    operator: OperatorContext = OperatorDep,
) -> dict:
    agent = get_agent(db, agent_id)
    if not agent:
        raise api_error("AGENT_NOT_FOUND", f"Agent '{agent_id}' not found", get_request_id(request), 404)
    assert_org_resource(agent.organization_id, operator)
    return {
        "id": agent.id, "name": agent.name, "owner": agent.owner, "version": agent.version,
        "status": agent.status, "allowed_tools": agent.allowed_tools, "policy_id": agent.policy_id,
        "limits": agent.limits, "last_seen": agent.last_seen,
    }


@router.post("/{agent_id}/kill-switch")
def agent_kill_switch(
    agent_id: str,
    body: AgentKillSwitchRequest,
    request: Request,
    db: Session = Depends(get_db),
    operator: OperatorContext = OperatorDep,
) -> dict:
    req_id = get_request_id(request)
    agent = get_agent(db, agent_id)
    if not agent:
        raise api_error("AGENT_NOT_FOUND", f"Agent '{agent_id}' not found", req_id, 404)
    agent.status = "DISABLED" if body.enabled else "ACTIVE"
    agent.updated_at = now()
    db.commit()
    record_audit(
        db=db, event_type="AGENT_KILL_SWITCH", action_id=None, approval_id=None,
        request_id=req_id, actor=body.actor,
        data={"agent_id": agent_id, "status": agent.status, "reason": body.reason},
        organization_id=agent.organization_id,
    )
    if body.enabled:
        create_incident(
            db, "AGENT_DISABLED", "HIGH", f"Agent {agent_id} disabled: {body.reason}",
            ["AGENT_DISABLED"], action_id=None, organization_id=agent.organization_id,
        )
    return {"agent_id": agent_id, "status": agent.status, "reason": body.reason}
