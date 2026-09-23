"""Tool registry."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth import OperatorContext, OperatorDep
from app.core.http import api_error, get_request_id
from app.database import get_db
from app.models import ToolModel
from app.registry import ensure_registry
from app.tenant import org_filter

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


@router.get("")
def list_tools(db: Session = Depends(get_db), operator: OperatorContext = OperatorDep) -> list[dict]:
    ensure_registry(db)
    tools = org_filter(db.query(ToolModel), ToolModel, operator).all()
    return [{
        "id": t.id, "name": t.name, "version": t.version, "endpoint": t.endpoint,
        "protocol": t.protocol, "risk_class": t.risk_class, "permission_scope": t.permission_scope,
        "input_schema": t.input_schema, "output_schema": t.output_schema, "enabled": t.enabled,
    } for t in tools]


@router.get("/{tool_id}")
def get_tool_detail(tool_id: str, request: Request, db: Session = Depends(get_db)) -> dict:
    tool = db.query(ToolModel).filter(ToolModel.id == tool_id).first()
    if not tool:
        raise api_error("TOOL_NOT_REGISTERED", f"Tool '{tool_id}' not found", get_request_id(request), 404)
    return {
        "id": tool.id, "name": tool.name, "version": tool.version, "endpoint": tool.endpoint,
        "risk_class": tool.risk_class, "permission_scope": tool.permission_scope,
        "input_schema": tool.input_schema, "enabled": tool.enabled,
    }
