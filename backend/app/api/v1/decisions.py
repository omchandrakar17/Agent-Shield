"""ADK-style tool-call decision API."""

from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.runtime.auth import RuntimeDep
from app.schemas.requests import ToolCallDecisionRequest
from app.services.action_service import enforce_tool_call

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])


@router.post("/tool-call")
def tool_call_decision(
    body: ToolCallDecisionRequest,
    request: Request,
    db: Session = Depends(get_db),
    _runtime: object = RuntimeDep,
) -> dict:
    target = body.context.get("target", f"order:{body.arguments.get('order_id', '2481')}")
    return enforce_tool_call(
        agent_id=body.agent_id, action_type=body.tool_id, target=target,
        payload=body.arguments, idempotency_key=body.idempotency_key or str(uuid4()),
        execution_id=body.execution_id, request=request, db=db,
    )
