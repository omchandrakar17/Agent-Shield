"""Dry-run policy replay."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth import OperatorContext, OperatorDep
from app.core.http import api_error, get_request_id
from app.database import get_db
from app.models import ActionModel
from app.policy_engine import evaluate_action
from app.schemas.requests import ReplayRequest
from app.services.action_service import run_tool_execution

router = APIRouter(prefix="/api/v1/replay", tags=["replay"])


@router.post("")
def replay_action(
    body: ReplayRequest,
    request: Request,
    db: Session = Depends(get_db),
    operator: OperatorContext = OperatorDep,
) -> dict:
    req_id = get_request_id(request)
    action = db.query(ActionModel).filter(ActionModel.id == body.action_id).first()
    if not action:
        raise api_error("ACTION_NOT_FOUND", f"Action '{body.action_id}' not found", req_id, 404)

    status, risk, reason, pol_id, pol_ver, matched_rule = evaluate_action(
        action.action_type, action.target, action.payload, db
    )
    dry_result = run_tool_execution(action.action_type, action.target, action.payload, dry_run=True)

    return {
        "action_id": action.id,
        "replay_mode": "DRY_RUN",
        "original_status": action.status,
        "replayed_decision": status.value,
        "policy_version": pol_ver,
        "matched_rule_id": matched_rule,
        "arguments_hash": action.arguments_hash,
        "risk_level": risk,
        "reason": reason,
        "dry_run_result": dry_result,
        "destructive_executed": False,
    }
