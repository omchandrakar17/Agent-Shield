"""Agent execution sessions and runner."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.agents.planner import plan_tool_calls
from app.core.http import api_error, get_request_id
from app.database import get_db
from app.execution_budget import check_execution_budget
from app.models import ActionModel, ExecutionModel, TraceSpanModel
from app.registry import get_agent
from app.runtime.agent_guard import assert_agent_executable, resolve_organization_id
from app.runtime.auth import RuntimeDep
from app.runtime.kill_switch import is_execution_blocked
from app.schemas.requests import ExecutionRunRequest, ExecutionStartRequest
from app.security import now
from app.execution_budget import get_or_create_execution
from app.services.action_service import enforce_tool_call, serialize_action
from app.services.trace_service import add_trace_span

router = APIRouter(prefix="/api/v1/executions", tags=["executions"])


@router.post("")
def start_execution(
    body: ExecutionStartRequest,
    request: Request,
    db: Session = Depends(get_db),
    _runtime: object = RuntimeDep,
) -> dict:
    req_id = get_request_id(request)
    agent = get_agent(db, body.agent_id)
    if not agent:
        raise api_error("AGENT_NOT_FOUND", f"Agent '{body.agent_id}' not found", req_id, 404)

    organization_id = resolve_organization_id(agent)
    blocked, kill_reason, kill_scope = is_execution_blocked(db, organization_id, body.agent_id, "*")
    if blocked:
        raise api_error("KILL_SWITCH_ACTIVE", "Cannot start execution while kill switch is active", req_id, 423,
                        {"kill_switch_reason": kill_reason, "scope": kill_scope})

    executable, exec_code, exec_msg = assert_agent_executable(agent)
    if not executable:
        raise api_error(exec_code, exec_msg, req_id, 423)

    limits = agent.limits or {}
    execution = get_or_create_execution(
        db, None, body.agent_id, body.session_id, body.user_request, limits, organization_id=organization_id
    )
    add_trace_span(db, "USER_REQUEST", "OK",
                   {"user_request": body.user_request, "agent_id": body.agent_id},
                   execution_id=execution.id)
    db.commit()
    return {
        "execution_id": execution.id, "agent_id": body.agent_id,
        "session_id": body.session_id, "status": execution.status, "user_request": body.user_request,
    }


@router.get("/{execution_id}")
def get_execution(
    execution_id: str,
    request: Request,
    db: Session = Depends(get_db),
    _runtime: object = RuntimeDep,
) -> dict:
    execution = db.query(ExecutionModel).filter(ExecutionModel.id == execution_id).first()
    if not execution:
        raise api_error("EXECUTION_NOT_FOUND", f"Execution '{execution_id}' not found", get_request_id(request), 404)
    actions = db.query(ActionModel).filter(ActionModel.execution_id == execution_id).order_by(ActionModel.created_at).all()
    action_ids = [a.id for a in actions]
    span_filters = [TraceSpanModel.execution_id == execution_id]
    if action_ids:
        span_filters.append(TraceSpanModel.action_id.in_(action_ids))
    spans = db.query(TraceSpanModel).filter(or_(*span_filters)).order_by(TraceSpanModel.start_time).all()
    return {
        "execution_id": execution.id, "agent_id": execution.agent_id,
        "user_request": execution.user_request, "status": execution.status,
        "tool_call_count": execution.tool_call_count, "started_at": execution.started_at,
        "completed_at": execution.completed_at,
        "actions": [serialize_action(a, db) for a in actions],
        "spans": [{"span_name": s.span_name, "status": s.status, "metadata": s.metadata_json,
                   "duration_ms": s.duration_ms} for s in spans],
    }


@router.post("/{execution_id}/run")
def run_agent_execution(
    execution_id: str,
    body: ExecutionRunRequest,
    request: Request,
    db: Session = Depends(get_db),
    _runtime: object = RuntimeDep,
) -> dict:
    req_id = get_request_id(request)
    execution = db.query(ExecutionModel).filter(ExecutionModel.id == execution_id).first()
    if not execution:
        raise api_error("EXECUTION_NOT_FOUND", f"Execution '{execution_id}' not found", req_id, 404)

    execution.user_request = body.user_request
    agent = get_agent(db, execution.agent_id)
    planned, plan_meta = plan_tool_calls(
        body.user_request,
        allowed_tools=agent.allowed_tools if agent else None,
        agent_model_provider=agent.model_provider if agent else None,
    )
    results = []

    add_trace_span(db, "MODEL_CALL", "OK", {
        "planned_tools": [p["tool_id"] for p in planned],
        "user_request": body.user_request,
        "planner": plan_meta.get("planner"),
        "model": plan_meta.get("model"),
    }, execution_id=execution_id)

    for i, plan in enumerate(planned):
        budget_ok, budget_code = check_execution_budget(db, execution, plan["tool_id"])
        if not budget_ok:
            execution.status = "BUDGET_EXCEEDED"
            execution.completed_at = now()
            db.commit()
            break

        try:
            action_result = enforce_tool_call(
                agent_id=execution.agent_id,
                action_type=plan["tool_id"],
                target=plan["target"],
                payload=plan["payload"],
                idempotency_key=f"{execution_id}-{plan['tool_id']}-{i}",
                execution_id=execution_id,
                request=request,
                db=db,
            )
            results.append(action_result)
            if action_result["status"] in ("BLOCKED", "REQUIRE_APPROVAL"):
                execution.status = "PAUSED" if action_result["status"] == "REQUIRE_APPROVAL" else "TERMINATED"
                break
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
            results.append({"error": detail, "tool_id": plan["tool_id"], "status": "BLOCKED"})
            execution.status = "TERMINATED"
            break

    if execution.status == "RUNNING":
        execution.status = "COMPLETED"
        execution.completed_at = now()
    db.commit()

    return {
        "execution_id": execution_id,
        "status": execution.status,
        "tool_calls": len(results),
        "results": results,
        "planner": plan_meta,
        "prompt_injection_detected": plan_meta.get("prompt_injection_detected", False),
    }
