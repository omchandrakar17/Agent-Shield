"""Runtime action gateway routes."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.auth import OperatorContext, OperatorDep
from app.core.events import publish_event
from app.core.http import api_error, get_request_id
from app.core.state_machine import transition_action
from app.database import get_db
from app.models import ActionModel, ApprovalModel, AuditEventModel, TraceSpanModel
from app.policy_engine import ActionStatus
from app.runtime.auth import RuntimeDep
from app.schemas.requests import ActionRequest
from app.security import now
from app.services.action_service import enforce_tool_call, serialize_action
from app.services.approval_service import check_and_expire_approvals
from app.tenant import org_filter

router = APIRouter(prefix="/api/v1/actions", tags=["actions"])


@router.post("")
def create_action(
    body: ActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    _runtime: object = RuntimeDep,
) -> dict:
    return enforce_tool_call(
        agent_id=body.agent_id,
        action_type=body.action_type,
        target=body.target,
        payload=body.payload,
        idempotency_key=body.idempotency_key,
        execution_id=body.execution_id,
        request=request,
        db=db,
    )


@router.get("")
def get_actions(
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    operator: OperatorContext = OperatorDep,
) -> list[dict]:
    check_and_expire_approvals(db)
    query = org_filter(db.query(ActionModel), ActionModel, operator)
    if status:
        query = query.filter(ActionModel.status == status.upper())
    actions = query.order_by(ActionModel.created_at.desc()).limit(limit).all()
    return [serialize_action(a, db) for a in actions]


@router.get("/{action_id}")
def get_action(
    action_id: str,
    request: Request,
    db: Session = Depends(get_db),
    _runtime: object = RuntimeDep,
) -> dict:
    check_and_expire_approvals(db)
    action = db.query(ActionModel).filter(ActionModel.id == action_id).first()
    if not action:
        raise api_error("ACTION_NOT_FOUND", f"Action '{action_id}' was not found", get_request_id(request), 404)
    return serialize_action(action, db)


@router.post("/{action_id}/cancel")
def cancel_action(
    action_id: str,
    request: Request,
    db: Session = Depends(get_db),
    operator: OperatorContext = OperatorDep,
) -> dict:
    req_id = get_request_id(request)
    action = db.query(ActionModel).filter(ActionModel.id == action_id).first()
    if not action:
        raise api_error("ACTION_NOT_FOUND", f"Action '{action_id}' was not found", req_id, 404)

    transition_action(
        action=action,
        new_status=ActionStatus.cancelled.value,
        reason="Cancelled by operator",
        request_id=req_id,
        db=db,
    )

    approval = db.query(ApprovalModel).filter(ApprovalModel.action_id == action_id).first()
    if approval and approval.status == "PENDING":
        approval.status = "CANCELLED"
        approval.decided_at = now()

    db.commit()
    res = serialize_action(action, db)
    publish_event("action.updated", res)
    return res


@router.get("/{action_id}/trace")
def get_action_trace(
    action_id: str,
    request: Request,
    db: Session = Depends(get_db),
    _runtime: object = RuntimeDep,
) -> dict:
    action = db.query(ActionModel).filter(ActionModel.id == action_id).first()
    if not action:
        raise api_error("ACTION_NOT_FOUND", f"Action '{action_id}' was not found", get_request_id(request), 404)

    spans = db.query(TraceSpanModel).filter(TraceSpanModel.action_id == action_id).order_by(TraceSpanModel.start_time.asc()).all()
    audit_events = db.query(AuditEventModel).filter(AuditEventModel.action_id == action_id).order_by(AuditEventModel.created_at.asc()).all()

    return {
        "action_id": action_id,
        "status": action.status,
        "risk_level": action.risk_level,
        "latency_ms": action.latency_ms,
        "matched_rule_id": action.matched_rule_id,
        "evidence": action.evidence,
        "spans": [
            {
                "id": s.id,
                "span_name": s.span_name,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "duration_ms": s.duration_ms,
                "status": s.status,
                "metadata": s.metadata_json,
            }
            for s in spans
        ],
        "audit_events": [
            {
                "id": a.id,
                "event_type": a.event_type,
                "actor": a.actor,
                "created_at": a.created_at,
                "request_id": a.request_id,
                "data": a.data,
                "evidence": a.evidence,
            }
            for a in audit_events
        ],
    }

