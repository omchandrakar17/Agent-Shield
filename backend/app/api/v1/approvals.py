"""Human approval workflow."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth import OperatorContext, OperatorDep
from app.core.events import publish_event
from app.core.http import api_error, get_request_id
from app.core.state_machine import transition_action
from app.database import get_db
from app.models import ActionModel, ApprovalModel
from app.policy_engine import ActionStatus
from app.runtime.kill_switch import is_execution_blocked
from app.schemas.requests import ApprovalDecisionRequest
from app.security import canonical_hash, generate_approval_fingerprint, now
from app.services.action_service import run_tool_execution, serialize_action
from app.services.approval_service import check_and_expire_approvals
from app.services.audit_service import record_audit
from app.services.trace_service import add_trace_span
from app.tenant import assert_org_resource, org_filter

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


@router.get("")
def get_approvals(
    status: str | None = None,
    db: Session = Depends(get_db),
    operator: OperatorContext = OperatorDep,
) -> list[dict]:
    check_and_expire_approvals(db)
    query = org_filter(db.query(ApprovalModel), ApprovalModel, operator)
    if status:
        query = query.filter(ApprovalModel.status == status.upper())
    approvals = query.order_by(ApprovalModel.requested_at.desc()).all()
    return [
        {
            "id": a.id,
            "action_id": a.action_id,
            "status": a.status,
            "arguments_hash": a.arguments_hash,
            "fingerprint": a.fingerprint,
            "requested_at": a.requested_at,
            "expires_at": a.expires_at,
            "decided_at": a.decided_at,
            "reviewer": a.reviewer,
            "reason": a.reason,
        }
        for a in approvals
    ]


@router.post("/{approval_id}/decision")
def decide_approval(
    approval_id: str,
    body: ApprovalDecisionRequest,
    request: Request,
    db: Session = Depends(get_db),
    operator: OperatorContext = OperatorDep,
) -> dict:
    req_id = get_request_id(request)
    decision = body.decision.lower()
    if decision not in {"approved", "denied"}:
        raise api_error("INVALID_DECISION", "Decision must be approved or denied", req_id)

    check_and_expire_approvals(db)
    approval = db.query(ApprovalModel).filter(ApprovalModel.id == approval_id).first()
    if not approval:
        raise api_error("APPROVAL_NOT_FOUND", f"Approval '{approval_id}' was not found", req_id, 404)

    if approval.status == "EXPIRED":
        raise api_error("APPROVAL_EXPIRED", "Approval has expired and cannot be decided", req_id, 409)

    if approval.status != "PENDING":
        raise api_error(
            "APPROVAL_ALREADY_DECIDED",
            f"Approval is no longer pending (current status: {approval.status})",
            req_id,
            409,
        )

    action = db.query(ActionModel).filter(ActionModel.id == approval.action_id).first()
    if not action:
        raise api_error("ACTION_NOT_FOUND", "Associated action not found", req_id, 404)
    assert_org_resource(action.organization_id, operator)

    current_payload_hash = canonical_hash(action.payload)
    if current_payload_hash != approval.arguments_hash:
        raise api_error(
            "ARGUMENT_MISMATCH",
            "Action arguments have been mutated since approval was created",
            req_id,
            409,
            {"expected": approval.arguments_hash, "actual": current_payload_hash},
        )

    expected_fp = generate_approval_fingerprint(
        action.id, action.agent_id, action.action_type, action.target, current_payload_hash, action.policy_version or 1
    )
    if approval.fingerprint and approval.fingerprint != expected_fp:
        raise api_error(
            "ARGUMENT_MISMATCH",
            "Approval binding fingerprint mismatch with current action context",
            req_id,
            409,
        )

    blocked, kill_reason, kill_scope = is_execution_blocked(
        db, action.organization_id, action.agent_id, action.action_type
    )
    current_time = now()
    approval.decided_at = current_time
    approval.reviewer = body.reviewer
    approval.reason = body.reason

    if decision == "approved":
        if blocked:
            approval.status = "BLOCKED"
            transition_action(
                action=action,
                new_status=ActionStatus.blocked.value,
                reason=f"Kill switch ({kill_scope}) enabled before approval execution: {kill_reason}",
                request_id=req_id,
                db=db,
            )
        else:
            approval.status = "APPROVED"
            transition_action(
                action=action,
                new_status=ActionStatus.approved.value,
                reason=f"Approved by {body.reviewer}",
                request_id=req_id,
                db=db,
            )
            tool_result = run_tool_execution(action.action_type, action.target, action.payload, dry_run=False)
            transition_action(
                action=action,
                new_status=ActionStatus.executed.value,
                reason=f"Executed after human approval by {body.reviewer}",
                request_id=req_id,
                db=db,
                result=tool_result,
            )
            add_trace_span(db, "TOOL_EXECUTION", "OK" if tool_result.get("success") else "FAILED",
                           {"reviewer": body.reviewer, "executed_after_approval": True, **tool_result}, action_id=action.id)
            add_trace_span(db, "TOOL_RESPONSE", "OK", {"response": tool_result}, action_id=action.id)
    else:
        approval.status = "DENIED"
        transition_action(
            action=action,
            new_status=ActionStatus.rejected.value,
            reason=body.reason or "Rejected by operator",
            request_id=req_id,
            db=db,
        )

    record_audit(
        db=db,
        event_type="APPROVAL_DECISION",
        action_id=action.id,
        approval_id=approval.id,
        request_id=req_id,
        actor=body.reviewer,
        data={
            "decision": approval.status,
            "action_status": action.status,
            "reviewer": body.reviewer,
            "reason": body.reason,
            "arguments_hash": approval.arguments_hash,
        },
        organization_id=action.organization_id,
    )

    db.commit()
    db.refresh(approval)
    db.refresh(action)

    approval_dict = {
        "id": approval.id,
        "action_id": approval.action_id,
        "status": approval.status,
        "arguments_hash": approval.arguments_hash,
        "fingerprint": approval.fingerprint,
        "requested_at": approval.requested_at,
        "expires_at": approval.expires_at,
        "decided_at": approval.decided_at,
        "reviewer": approval.reviewer,
        "reason": approval.reason,
    }
    action_dict = serialize_action(action, db)
    publish_event("approval.decided", approval_dict)
    publish_event("action.updated", action_dict)

    return {"approval": approval_dict, "action": action_dict}
