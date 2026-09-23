"""Approval lifecycle — expiry and decision helpers."""

from sqlalchemy.orm import Session

from app.core.events import publish_event
from app.core.state_machine import transition_action
from app.models import ActionModel, ApprovalModel
from app.policy_engine import ActionStatus
from app.security import now
from app.services.audit_service import record_audit


def check_and_expire_approvals(db: Session) -> None:
    current_time = now()
    expired_approvals = db.query(ApprovalModel).filter(
        ApprovalModel.status == "PENDING",
        ApprovalModel.expires_at != None,  # noqa: E711
        ApprovalModel.expires_at < current_time,
    ).all()

    for apr in expired_approvals:
        apr.status = "EXPIRED"
        apr.decided_at = current_time
        action = db.query(ActionModel).filter(ActionModel.id == apr.action_id).first()
        if action and action.status == ActionStatus.awaiting_approval.value:
            transition_action(
                action=action,
                new_status=ActionStatus.expired.value,
                reason="Approval TTL expired before operator review",
                request_id="sys-cron",
                db=db,
            )
        record_audit(
            db=db,
            event_type="APPROVAL_EXPIRED",
            action_id=apr.action_id,
            approval_id=apr.id,
            request_id="sys-cron",
            actor="system",
            data={"reason": "TTL expired"},
            organization_id=apr.organization_id,
        )
        publish_event("approval.expired", {"id": apr.id, "action_id": apr.action_id})
    if expired_approvals:
        db.commit()
