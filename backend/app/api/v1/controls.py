"""Legacy global kill switch controls."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth import OperatorContext, OperatorDep
from app.core.events import publish_event
from app.core.http import get_request_id
from app.database import get_db
from app.schemas.requests import KillSwitchRequest
from app.security import now
from app.services.audit_service import record_audit
from app.services.control_service import get_or_create_control

router = APIRouter(prefix="/api/v1/controls", tags=["controls"])


@router.get("")
def get_controls(db: Session = Depends(get_db), operator: OperatorContext = OperatorDep) -> dict:
    ctrl = get_or_create_control(db)
    return {
        "enabled": ctrl.enabled,
        "reason": ctrl.reason,
        "actor": ctrl.actor,
        "updated_at": ctrl.updated_at,
    }


@router.post("/kill-switch")
def set_kill_switch(
    body: KillSwitchRequest,
    request: Request,
    db: Session = Depends(get_db),
    operator: OperatorContext = OperatorDep,
) -> dict:
    req_id = get_request_id(request)
    ctrl = get_or_create_control(db)
    ctrl.enabled = body.enabled
    ctrl.reason = body.reason
    ctrl.actor = body.actor
    ctrl.updated_at = now()
    db.commit()

    record_audit(
        db=db,
        event_type="KILL_SWITCH_UPDATED",
        action_id=None,
        approval_id=None,
        request_id=req_id,
        actor=body.actor,
        data={"enabled": ctrl.enabled, "reason": ctrl.reason, "actor": ctrl.actor},
        organization_id=operator.organization_id,
    )
    result = {
        "enabled": ctrl.enabled,
        "reason": ctrl.reason,
        "actor": ctrl.actor,
        "updated_at": ctrl.updated_at,
    }
    publish_event("controls.updated", result)
    return result
