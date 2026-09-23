"""Tool gateway — shield check then business tool execution."""

from typing import Any

from sqlalchemy.orm import Session

from app.business_tools import execute_business_tool
from app.registry import agent_allows_tool, get_agent, get_tool
from app.runtime.agent_guard import NON_EXECUTABLE_STATUSES
from app.tool_schemas import TOOL_SCHEMAS


def validate_tool_schema(tool_id: str, payload: dict[str, Any]) -> tuple[bool, str]:
    schema = TOOL_SCHEMAS.get(tool_id)
    if not schema:
        return False, f"Tool '{tool_id}' has no registered schema"

    try:
        import jsonschema
        jsonschema.validate(instance=payload, schema=schema)
        return True, ""
    except ImportError:
        # Fallback basic validation if jsonschema not installed
        if tool_id == "issue_refund":
            amount = payload.get("amount")
            if not isinstance(amount, (int, float)) or amount <= 0:
                return False, "Refund amount must be a positive number"
        return True, ""
    except jsonschema.ValidationError as exc:
        return False, f"Schema validation failed: {exc.message}"


def check_agent_tool_access(db: Session, agent_id: str, tool_id: str) -> tuple[bool, str, str]:
    """Returns (allowed, error_code, message)."""
    agent = get_agent(db, agent_id)
    if not agent:
        return False, "AGENT_NOT_FOUND", f"Agent '{agent_id}' is not registered"
    if agent.status in NON_EXECUTABLE_STATUSES:
        return False, "AGENT_NOT_EXECUTABLE", f"Agent '{agent_id}' is {agent.status} and cannot execute tools"
    tool = get_tool(db, tool_id)
    if not tool:
        return False, "TOOL_NOT_REGISTERED", f"Tool '{tool_id}' is not registered"
    if not tool.enabled:
        return False, "TOOL_NOT_ALLOWED", f"Tool '{tool_id}' is disabled"
    if not agent_allows_tool(agent, tool_id):
        return False, "TOOL_NOT_ALLOWED", f"Tool '{tool_id}' is not permitted for agent '{agent_id}'"
    return True, "", ""


def execute_tool(
    tool_id: str,
    target: str,
    payload: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    return execute_business_tool(tool_id, target, payload, dry_run=dry_run)
