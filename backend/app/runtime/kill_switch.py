"""Scoped kill switch evaluation — GLOBAL, ORGANIZATION, AGENT, TOOL."""

from sqlalchemy.orm import Session

from app.models import ControlModel, KillSwitchModel


def get_or_create_global_control(db: Session) -> ControlModel:
    ctrl = db.query(ControlModel).filter(ControlModel.id == "system_kill_switch").first()
    if not ctrl:
        from app.security import now

        ctrl = ControlModel(id="system_kill_switch", enabled=False, reason="", actor="system", updated_at=now())
        db.add(ctrl)
        db.commit()
        db.refresh(ctrl)
    return ctrl


def is_execution_blocked(
    db: Session,
    organization_id: str,
    agent_id: str,
    tool_id: str,
) -> tuple[bool, str, str]:
    """Return (blocked, reason, scope)."""
    ctrl = get_or_create_global_control(db)
    if ctrl.enabled:
        return True, ctrl.reason or "Global kill switch active", "GLOBAL"

    switches = db.query(KillSwitchModel).filter(KillSwitchModel.enabled.is_(True)).all()
    for switch in switches:
        if switch.scope == "GLOBAL":
            return True, switch.reason or "Kill switch active", "GLOBAL"
        if switch.scope == "ORGANIZATION" and switch.organization_id == organization_id:
            return True, switch.reason or "Organization kill switch active", "ORGANIZATION"
        if switch.scope == "AGENT" and switch.target_id == agent_id:
            return True, switch.reason or f"Agent {agent_id} kill switch active", "AGENT"
        if switch.scope == "TOOL" and switch.target_id == tool_id:
            return True, switch.reason or f"Tool {tool_id} kill switch active", "TOOL"
    return False, "", ""


def upsert_scoped_kill_switch(
    db: Session,
    scope: str,
    enabled: bool,
    reason: str,
    actor_id: str,
    organization_id: str | None = None,
    target_id: str | None = None,
) -> KillSwitchModel:
    from uuid import uuid4

    from app.security import now

    query = db.query(KillSwitchModel).filter(KillSwitchModel.scope == scope)
    if scope == "ORGANIZATION":
        query = query.filter(KillSwitchModel.organization_id == organization_id)
    elif scope in {"AGENT", "TOOL"}:
        query = query.filter(KillSwitchModel.target_id == target_id)
    else:
        query = query.filter(KillSwitchModel.organization_id.is_(None), KillSwitchModel.target_id.is_(None))

    switch = query.first()
    ts = now()
    if not switch:
        switch = KillSwitchModel(
            id=f"ks-{uuid4().hex[:10]}",
            organization_id=organization_id,
            scope=scope,
            target_id=target_id,
            enabled=enabled,
            reason=reason,
            actor_id=actor_id,
            updated_at=ts,
        )
        db.add(switch)
    else:
        switch.enabled = enabled
        switch.reason = reason
        switch.actor_id = actor_id
        switch.updated_at = ts
    db.commit()
    db.refresh(switch)
    return switch
