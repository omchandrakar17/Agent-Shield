"""Audit log read API."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import OperatorContext, OperatorDep
from app.database import get_db
from app.models import AuditEventModel
from app.tenant import org_filter

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("")
def get_audit(
    action_id: str | None = None,
    event_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    operator: OperatorContext = OperatorDep,
) -> list[dict]:
    query = org_filter(db.query(AuditEventModel), AuditEventModel, operator)
    if action_id:
        query = query.filter(AuditEventModel.action_id == action_id)
    if event_type:
        query = query.filter(AuditEventModel.event_type == event_type)
    events = query.order_by(AuditEventModel.created_at.desc()).limit(limit).all()
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "action_id": e.action_id,
            "approval_id": e.approval_id,
            "request_id": e.request_id,
            "actor": e.actor,
            "reason_code": e.reason_code,
            "data": e.data,
            "evidence": e.evidence,
            "created_at": e.created_at,
        }
        for e in events
    ]
