"""Action status state machine."""

from sqlalchemy.orm import Session

from app.core.http import api_error
from app.models import ActionModel
from app.policy_engine import ActionStatus
from app.security import now
from app.services.audit_service import record_audit

ALLOWED_TRANSITIONS = {
    ActionStatus.submitted.value: {
        ActionStatus.executed.value,
        ActionStatus.awaiting_approval.value,
        ActionStatus.blocked.value,
        ActionStatus.failed.value,
    },
    ActionStatus.awaiting_approval.value: {
        ActionStatus.approved.value,
        ActionStatus.rejected.value,
        ActionStatus.expired.value,
        ActionStatus.cancelled.value,
        ActionStatus.blocked.value,
    },
    ActionStatus.approved.value: {
        ActionStatus.executed.value,
        ActionStatus.blocked.value,
        ActionStatus.failed.value,
    },
    ActionStatus.executed.value: set(),
    ActionStatus.rejected.value: set(),
    ActionStatus.expired.value: set(),
    ActionStatus.cancelled.value: set(),
    ActionStatus.blocked.value: set(),
    ActionStatus.failed.value: set(),
}


def ensure_action_transition_allowed(current_status: str, target_status: str, request_id: str) -> None:
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise api_error(
            "INVALID_TRANSITION",
            f"Action cannot transition from '{current_status}' to '{target_status}'",
            request_id,
            409,
        )


def transition_action(
    action: ActionModel,
    new_status: str,
    reason: str,
    request_id: str,
    db: Session,
    result: dict | None = None,
) -> None:
    ensure_action_transition_allowed(action.status, new_status, request_id)
    action.status = new_status
    action.reason = reason
    action.updated_at = now()
    if result is not None:
        action.result = result
    record_audit(
        db=db,
        event_type="ACTION_STATE_CHANGED",
        action_id=action.id,
        approval_id=action.approval_id,
        request_id=request_id,
        actor="system",
        data={"new_status": new_status, "reason": reason},
        organization_id=action.organization_id,
    )
