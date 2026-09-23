"""Runtime action gateway — enforce tool calls end-to-end."""

import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import Request
from sqlalchemy.orm import Session

from app.cloud.gateway import model_armor_gateway
from app.core.events import publish_event
from app.core.http import api_error, get_request_id
from app.execution_budget import check_execution_budget, get_or_create_execution, record_tool_call
from app.models import ActionModel, ApprovalModel
from app.policy_engine import DEFAULT_POLICY_ID, ActionStatus, evaluate_action
from app.registry import get_agent, get_tool
from app.runtime.agent_guard import assert_agent_executable, assert_execution_binding, resolve_organization_id
from app.runtime.kill_switch import is_execution_blocked
from app.runtime.rate_limit import check_rate_limit
from app.security import canonical_hash, generate_approval_fingerprint, now
from app.services.audit_service import record_audit
from app.services.incident_service import create_incident
from app.services.trace_service import add_trace_span
from app.tool_gateway import check_agent_tool_access, execute_tool, validate_tool_schema


def serialize_action(action: ActionModel, db: Session) -> dict:
    policy_info = {"id": action.policy_id or DEFAULT_POLICY_ID, "version": action.policy_version or 1}
    return {
        "id": action.id,
        "execution_id": action.execution_id,
        "agent_id": action.agent_id,
        "action_type": action.action_type,
        "target": action.target,
        "payload": action.payload,
        "idempotency_key": action.idempotency_key,
        "arguments_hash": action.arguments_hash,
        "status": action.status,
        "risk_level": action.risk_level,
        "reason": action.reason,
        "policy": policy_info,
        "matched_rule_id": action.matched_rule_id,
        "approval_id": action.approval_id,
        "result": action.result,
        "evidence": action.evidence,
        "latency_ms": action.latency_ms,
        "created_at": action.created_at,
        "updated_at": action.updated_at,
    }


def run_tool_execution(action_type: str, target: str, payload: dict, dry_run: bool = False) -> dict:
    return execute_tool(action_type, target, payload, dry_run=dry_run)


def create_blocked_action(
    db: Session,
    req_id: str,
    agent_id: str,
    action_type: str,
    target: str,
    payload: dict,
    idempotency_key: str,
    execution_id: str | None,
    reason: str,
    reason_code: str,
    matched_rule: str = "rule-default-deny",
    organization_id: str = "org-default",
) -> dict:
    action_id = "act-" + uuid4().hex[:10]
    payload_hash = canonical_hash(payload)
    create_incident(
        db,
        "UNAUTHORIZED_TOOL" if reason_code == "TOOL_NOT_ALLOWED" else reason_code,
        "CRITICAL" if action_type == "delete_customer" else "HIGH",
        reason,
        [reason_code],
        execution_id=execution_id,
        action_id=action_id,
        organization_id=organization_id,
    )
    add_trace_span(db, "TOOL_REQUEST", "BLOCKED", {"tool_id": action_type, "target": target}, action_id=action_id)
    add_trace_span(db, "POLICY_DECISION", "BLOCKED", {"reason": reason, "reason_code": reason_code}, action_id=action_id)
    action = ActionModel(
        id=action_id,
        organization_id=organization_id,
        execution_id=execution_id,
        agent_id=agent_id,
        action_type=action_type,
        target=target,
        payload=payload,
        idempotency_key=idempotency_key,
        fingerprint=canonical_hash({"agent_id": agent_id, "action_type": action_type, "target": target, "payload": payload}),
        arguments_hash=payload_hash,
        status=ActionStatus.blocked.value,
        risk_level="CRITICAL" if action_type == "delete_customer" else "HIGH",
        reason=reason,
        policy_id=DEFAULT_POLICY_ID,
        policy_version=1,
        matched_rule_id=matched_rule,
        approval_id=None,
        result=None,
        evidence={"decision_basis": reason, "reason_code": reason_code},
        created_at=now(),
        updated_at=now(),
        latency_ms=1.0,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    record_audit(
        db=db,
        event_type="ACTION_DECISION",
        action_id=action_id,
        approval_id=None,
        request_id=req_id,
        actor=agent_id,
        data={"status": "BLOCKED", "reason": reason, "reason_code": reason_code, "action_type": action_type},
        organization_id=organization_id,
    )
    action_dict = serialize_action(action, db)
    publish_event("action.created", action_dict)
    return action_dict


def enforce_tool_call(
    agent_id: str,
    action_type: str,
    target: str,
    payload: dict,
    idempotency_key: str,
    execution_id: str | None,
    request: Request,
    db: Session,
) -> dict:
    req_id = get_request_id(request)
    start_ts = time.perf_counter()

    existing = db.query(ActionModel).filter(ActionModel.idempotency_key == idempotency_key).first()
    if existing:
        body_fp = canonical_hash({"agent_id": agent_id, "action_type": action_type, "target": target, "payload": payload})
        if existing.fingerprint != body_fp:
            raise api_error(
                "IDEMPOTENCY_CONFLICT",
                "Idempotency key was reused with different arguments",
                req_id,
                409,
                {"existing_action_id": existing.id},
            )
        return serialize_action(existing, db)

    agent = get_agent(db, agent_id)
    if not agent:
        raise api_error("AGENT_NOT_FOUND", f"Agent '{agent_id}' is not registered", req_id, 404)

    organization_id = resolve_organization_id(agent)

    blocked, kill_reason, kill_scope = is_execution_blocked(db, organization_id, agent_id, action_type)
    if blocked:
        record_audit(
            db=db, event_type="ACTION_BLOCKED_BY_KILL_SWITCH", action_id=None, approval_id=None,
            request_id=req_id, actor=agent_id,
            data={"action_type": action_type, "target": target, "kill_switch_reason": kill_reason, "scope": kill_scope},
            organization_id=organization_id,
        )
        raise api_error("KILL_SWITCH_ACTIVE", "Execution blocked by kill switch", req_id, 423,
                        {"kill_switch_reason": kill_reason, "scope": kill_scope})

    executable, exec_code, exec_msg = assert_agent_executable(agent)
    if not executable:
        create_incident(db, exec_code, "HIGH", exec_msg, [exec_code],
                        execution_id=execution_id, organization_id=organization_id)
        raise api_error(exec_code, exec_msg, req_id, 423)

    if execution_id:
        try:
            assert_execution_binding(db, execution_id, agent_id)
        except ValueError:
            raise api_error("EXECUTION_AGENT_MISMATCH", "Execution does not belong to this agent", req_id, 409)

    allowed, err_code, err_msg = check_agent_tool_access(db, agent_id, action_type)
    if not allowed:
        return create_blocked_action(
            db, req_id, agent_id, action_type, target, payload, idempotency_key,
            execution_id, err_msg, err_code, matched_rule="rule-tool-deny",
            organization_id=organization_id,
        )

    tool = get_tool(db, action_type)
    if tool and tool.rate_limit_per_minute:
        rate_ok, rate_msg = check_rate_limit(f"{organization_id}:{agent_id}:{action_type}", tool.rate_limit_per_minute)
        if not rate_ok:
            create_incident(db, "RATE_LIMIT_EXCEEDED", "MEDIUM", rate_msg, ["RATE_LIMIT_EXCEEDED"],
                            execution_id=execution_id, organization_id=organization_id)
            raise api_error("RATE_LIMIT_EXCEEDED", rate_msg, req_id, 429)

    execution = None
    if execution_id:
        execution = get_or_create_execution(
            db, execution_id, agent_id, "sess-inline", "tool-call", organization_id=organization_id
        )
        budget_ok, budget_code = check_execution_budget(db, execution, action_type)
        if not budget_ok:
            create_incident(db, "BUDGET_EXCEEDED", "HIGH", f"Execution budget exceeded: {budget_code}",
                            [budget_code], execution_id=execution_id, organization_id=organization_id)
            raise api_error("BUDGET_EXCEEDED", f"Execution budget exceeded: {budget_code}", req_id, 429)

    schema_ok, schema_err = validate_tool_schema(action_type, payload)
    if not schema_ok:
        raise api_error("SCHEMA_INVALID", schema_err, req_id, 400)

    armor_result = model_armor_gateway.inspect_payload(action_type, target, payload)
    if not armor_result.passed:
        create_incident(db, "PROMPT_INJECTION", "HIGH", armor_result.reason, ["MODEL_ARMOR_BLOCK"],
                        execution_id=execution_id, organization_id=organization_id)
        record_audit(db=db, event_type="ACTION_BLOCKED_BY_MODEL_ARMOR", action_id=None, approval_id=None,
                     request_id=req_id, actor=agent_id,
                     data={"action_type": action_type, "target": target, "reason": armor_result.reason},
                     organization_id=organization_id)
        raise api_error("POLICY_BLOCK", armor_result.reason, req_id, 400, armor_result.to_dict())

    action_id = "act-" + uuid4().hex[:10]
    payload_hash = canonical_hash(payload)
    full_fingerprint = canonical_hash({"agent_id": agent_id, "action_type": action_type, "target": target, "payload": payload})

    add_trace_span(db, "TOOL_REQUEST", "OK",
                   {"tool_id": action_type, "target": target, "agent_id": agent_id}, action_id=action_id)

    eval_perf_start = time.perf_counter()
    status, risk, reason, pol_id, pol_ver, matched_rule = evaluate_action(action_type, target, payload, db)
    eval_duration_ms = round((time.perf_counter() - eval_perf_start) * 1000, 2)

    add_trace_span(db, "POLICY_DECISION", status.value, {
        "policy_id": pol_id, "policy_version": pol_ver, "matched_rule_id": matched_rule,
        "risk_level": risk, "effect": status.value, "reason": reason,
    }, duration_ms=eval_duration_ms, action_id=action_id)

    evidence = {
        "matched_rule_id": matched_rule, "policy_version": pol_ver, "payload_hash": payload_hash,
        "decision_basis": reason, "risk_level": risk,
    }

    approval_id = None
    result = None

    if status == ActionStatus.executed:
        tool_result = run_tool_execution(action_type, target, payload, dry_run=False)
        add_trace_span(db, "TOOL_EXECUTION", "OK" if tool_result.get("success") else "FAILED", tool_result, action_id=action_id)
        add_trace_span(db, "TOOL_RESPONSE", "OK", {"response": tool_result}, action_id=action_id)
        result = tool_result
        if execution:
            record_tool_call(db, execution, action_type, "ALLOW")
    elif status == ActionStatus.blocked:
        create_incident(db, "POLICY_VIOLATION", risk, reason, [matched_rule],
                        execution_id=execution_id, action_id=action_id, organization_id=organization_id)
        if execution:
            record_tool_call(db, execution, action_type, "BLOCK")
    elif status == ActionStatus.awaiting_approval:
        approval_id = "apr-" + uuid4().hex[:10]
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        approval_fp = generate_approval_fingerprint(action_id, agent_id, action_type, target, payload_hash, pol_ver)
        db.add(ApprovalModel(
            id=approval_id, organization_id=organization_id, action_id=action_id, status="PENDING",
            arguments_hash=payload_hash, fingerprint=approval_fp, requested_at=now(), expires_at=expires_at,
        ))
        add_trace_span(db, "APPROVAL_WAIT", "PENDING", {"approval_id": approval_id, "expires_at": expires_at}, action_id=action_id)
        publish_event("approval.created", {
            "id": approval_id, "action_id": action_id, "status": "PENDING",
            "arguments_hash": payload_hash, "fingerprint": approval_fp, "expires_at": expires_at,
        })
        if execution:
            record_tool_call(db, execution, action_type, "REQUIRE_APPROVAL")

    total_latency_ms = round((time.perf_counter() - start_ts) * 1000, 2)

    action = ActionModel(
        id=action_id, organization_id=organization_id, execution_id=execution_id, agent_id=agent_id,
        action_type=action_type, target=target, payload=payload, idempotency_key=idempotency_key,
        fingerprint=full_fingerprint, arguments_hash=payload_hash, status=status.value, risk_level=risk,
        reason=reason, policy_id=pol_id, policy_version=pol_ver, matched_rule_id=matched_rule,
        approval_id=approval_id, result=result, evidence=evidence,
        created_at=now(), updated_at=now(), latency_ms=total_latency_ms,
    )
    db.add(action)
    agent.last_seen = now()
    db.commit()
    db.refresh(action)

    record_audit(db=db, event_type="ACTION_DECISION", action_id=action_id, approval_id=approval_id,
                 request_id=req_id, actor=agent_id,
                 data={"status": status.value, "risk_level": risk, "reason": reason,
                       "policy_version": pol_ver, "matched_rule_id": matched_rule,
                       "action_type": action_type, "target": target, "latency_ms": total_latency_ms},
                 evidence=evidence, organization_id=organization_id)

    action_dict = serialize_action(action, db)
    publish_event("action.created", action_dict)
    return action_dict
