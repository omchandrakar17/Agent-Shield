"""Loop controls and execution session budget enforcement."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import ExecutionModel
from app.security import now

DEFAULT_MAX_TOOL_CALLS = 12
DEFAULT_MAX_EXECUTION_SECONDS = 45
DEFAULT_MAX_SAME_TOOL_REPEATS = 3


def get_or_create_execution(
    db: Session,
    execution_id: str | None,
    agent_id: str,
    session_id: str,
    user_request: str,
    limits: dict[str, Any] | None = None,
    organization_id: str = "org-default",
) -> ExecutionModel:
    if execution_id:
        existing = db.query(ExecutionModel).filter(ExecutionModel.id == execution_id).first()
        if existing:
            if existing.agent_id != agent_id:
                raise ValueError("EXECUTION_AGENT_MISMATCH")
            return existing

    limits = limits or {}
    exe = ExecutionModel(
        id=execution_id or f"exe-{__import__('uuid').uuid4().hex[:10]}",
        organization_id=organization_id,
        agent_id=agent_id,
        session_id=session_id,
        user_request=user_request,
        status="RUNNING",
        tool_call_count=0,
        tool_call_history=[],
        max_tool_calls=int(limits.get("max_tool_calls", DEFAULT_MAX_TOOL_CALLS)),
        max_execution_seconds=int(limits.get("max_execution_seconds", DEFAULT_MAX_EXECUTION_SECONDS)),
        max_same_tool_repeats=int(limits.get("max_same_tool_repeats", DEFAULT_MAX_SAME_TOOL_REPEATS)),
        started_at=now(),
        completed_at=None,
    )
    db.add(exe)
    db.commit()
    db.refresh(exe)
    return exe


def check_execution_budget(db: Session, execution: ExecutionModel, tool_id: str) -> tuple[bool, str | None]:
    """Returns (allowed, reason_code)."""
    if execution.status in {"TERMINATED", "BUDGET_EXCEEDED", "COMPLETED"}:
        return False, "EXECUTION_TERMINATED"

    if execution.tool_call_count >= execution.max_tool_calls:
        execution.status = "BUDGET_EXCEEDED"
        execution.completed_at = now()
        db.commit()
        return False, "BUDGET_EXCEEDED"

    started = datetime.fromisoformat(execution.started_at.replace("Z", "+00:00"))
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    if elapsed > execution.max_execution_seconds:
        execution.status = "BUDGET_EXCEEDED"
        execution.completed_at = now()
        db.commit()
        return False, "BUDGET_EXCEEDED"

    history = execution.tool_call_history or []
    same_tool_count = sum(1 for h in history if h.get("tool_id") == tool_id)
    if same_tool_count >= execution.max_same_tool_repeats:
        execution.status = "BUDGET_EXCEEDED"
        execution.completed_at = now()
        db.commit()
        return False, "BUDGET_EXCEEDED"

    return True, None


def record_tool_call(db: Session, execution: ExecutionModel, tool_id: str, decision: str) -> None:
    history = list(execution.tool_call_history or [])
    history.append({"tool_id": tool_id, "decision": decision, "at": now()})
    execution.tool_call_history = history
    execution.tool_call_count = (execution.tool_call_count or 0) + 1
    db.commit()
