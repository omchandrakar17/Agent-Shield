"""Distributed trace span recording."""

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import TraceSpanModel
from app.security import now


def add_trace_span(
    db: Session,
    span_name: str,
    status: str,
    metadata: dict | None = None,
    duration_ms: float = 0.5,
    action_id: str | None = None,
    execution_id: str | None = None,
) -> TraceSpanModel:
    resolved_action_id = action_id or execution_id
    span = TraceSpanModel(
        id=str(uuid4()),
        action_id=resolved_action_id,
        execution_id=execution_id,
        span_name=span_name,
        start_time=now(),
        end_time=now(),
        duration_ms=duration_ms,
        status=status,
        metadata_json=metadata or {},
    )
    db.add(span)
    return span
