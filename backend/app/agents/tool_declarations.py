"""Gemini function declarations built from registered tool schemas."""

from typing import Any

from app.tool_schemas import TOOL_SCHEMAS

# Human-readable descriptions for the model (recommendations only — AgentShield enforces)
TOOL_DESCRIPTIONS: dict[str, str] = {
    "get_order": "Look up order status and shipping details by order ID.",
    "get_customer": "Retrieve customer profile information by customer ID.",
    "search_refund_policy": "Search the organization's refund policy before issuing refunds.",
    "issue_refund": "Issue a monetary refund for an order. High-impact financial action.",
    "update_shipping": "Update the shipping address on an order.",
    "delete_customer": "Permanently delete or disable a customer account. Critical destructive action.",
}


def build_function_declarations(allowed_tools: list[str] | None = None) -> list[dict[str, Any]]:
    """Build Gemini-compatible function declarations for the agent's allowlist."""
    tool_ids = allowed_tools if allowed_tools else list(TOOL_SCHEMAS.keys())
    declarations = []
    for tool_id in tool_ids:
        schema = TOOL_SCHEMAS.get(tool_id)
        if not schema:
            continue
        declarations.append({
            "name": tool_id,
            "description": TOOL_DESCRIPTIONS.get(tool_id, f"Execute tool {tool_id}"),
            "parameters": schema,
        })
    return declarations
