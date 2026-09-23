"""Scoped kill switch management API."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import OperatorDep, require_permission
from app.auth import OperatorContext
from app.core.rbac import Permission
from app.database import get_db
from app.models import KillSwitchModel
from app.runtime.kill_switch import get_or_create_global_control, upsert_scoped_kill_switch

router = APIRouter(prefix="/api/v1/kill-switches", tags=["kill-switches"])


class KillSwitchSetRequest(BaseModel):
    scope: str = Field(pattern="^(GLOBAL|ORGANIZATION|AGENT|TOOL)$")
    enabled: bool
    reason: str = Field(min_length=1)
    target_id: str | None = None


@router.get("")
def list_kill_switches(
    operator: OperatorContext = Depends(require_permission(Permission.KILL_SWITCH)),
    db: Session = Depends(get_db),
) -> list[dict]:
    query = db.query(KillSwitchModel)
    if operator.role != "PLATFORM_ADMIN":
        query = query.filter(
            (KillSwitchModel.organization_id == operator.organization_id)
            | (KillSwitchModel.scope == "GLOBAL")
            | (KillSwitchModel.organization_id.is_(None))
        )
    switches = query.order_by(KillSwitchModel.updated_at.desc()).all()
    ctrl = get_or_create_global_control(db)
    result = [
        {
            "id": "legacy-global",
            "scope": "GLOBAL",
            "target_id": None,
            "organization_id": None,
            "enabled": ctrl.enabled,
            "reason": ctrl.reason,
            "actor_id": ctrl.actor,
            "updated_at": ctrl.updated_at,
            "source": "controls",
        }
    ]
    result.extend(
        {
            "id": s.id,
            "scope": s.scope,
            "target_id": s.target_id,
            "organization_id": s.organization_id,
            "enabled": s.enabled,
            "reason": s.reason,
            "actor_id": s.actor_id,
            "updated_at": s.updated_at,
            "source": "kill_switches",
        }
        for s in switches
    )
    return result


@router.post("")
def set_scoped_kill_switch(
    body: KillSwitchSetRequest,
    operator: OperatorContext = Depends(require_permission(Permission.KILL_SWITCH)),
    db: Session = Depends(get_db),
) -> dict:
    org_id = operator.organization_id
    target_id = body.target_id

    if body.scope == "ORGANIZATION" and operator.role != "PLATFORM_ADMIN":
        target_id = None
    if body.scope in {"AGENT", "TOOL"} and not target_id:
        raise HTTPException(
            status_code=400,
            detail={"code": "TARGET_REQUIRED", "message": f"target_id required for {body.scope} scope"},
        )
    if body.scope == "GLOBAL" and operator.role != "PLATFORM_ADMIN":
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Only platform admins can set global kill switches"},
        )

    if body.scope == "GLOBAL":
        ctrl = get_or_create_global_control(db)
        ctrl.enabled = body.enabled
        ctrl.reason = body.reason
        ctrl.actor = operator.user_id
        from app.security import now

        ctrl.updated_at = now()
        db.commit()
        switch = upsert_scoped_kill_switch(
            db, "GLOBAL", body.enabled, body.reason, operator.user_id, None, None
        )
        return {"id": switch.id, "scope": "GLOBAL", "enabled": body.enabled, "reason": body.reason}

    switch = upsert_scoped_kill_switch(
        db,
        body.scope,
        body.enabled,
        body.reason,
        operator.user_id,
        org_id if body.scope == "ORGANIZATION" else org_id,
        target_id,
    )
    return {
        "id": switch.id,
        "scope": switch.scope,
        "target_id": switch.target_id,
        "organization_id": switch.organization_id,
        "enabled": switch.enabled,
        "reason": switch.reason,
    }
