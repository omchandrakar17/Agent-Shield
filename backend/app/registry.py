"""Agent and tool registry seed data and helpers."""

from sqlalchemy.orm import Session

from app.models import AgentModel, ToolModel
from app.security import now
from app.services.bootstrap import DEFAULT_ORG_ID
from app.tool_schemas import TOOL_SCHEMAS

DEFAULT_AGENTS = [
    {
        "id": "support-agent",
        "name": "Support Agent",
        "owner": "platform-team",
        "version": "2026.09.1",
        "status": "ACTIVE",
        "allowed_tools": ["get_order", "get_customer", "search_refund_policy", "issue_refund", "update_shipping"],
        "model_provider": "gemini",
        "policy_id": "default-policy",
        "limits": {
            "max_tool_calls": 12,
            "max_execution_seconds": 45,
            "max_autonomous_refund_inr": 10000,
        },
    },
]

DEFAULT_TOOLS = [
    {
        "id": "get_order",
        "name": "get_order",
        "version": "1.0",
        "endpoint": "/api/v1/business/orders/{order_id}",
        "protocol": "REST",
        "risk_class": "LOW",
        "permission_scope": "order:read",
        "input_schema": TOOL_SCHEMAS["get_order"],
        "output_schema": {"type": "object"},
        "enabled": True,
    },
    {
        "id": "get_customer",
        "name": "get_customer",
        "version": "1.0",
        "endpoint": "/api/v1/business/customers/{customer_id}",
        "protocol": "REST",
        "risk_class": "LOW",
        "permission_scope": "customer:read",
        "input_schema": TOOL_SCHEMAS["get_customer"],
        "output_schema": {"type": "object"},
        "enabled": True,
    },
    {
        "id": "search_refund_policy",
        "name": "search_refund_policy",
        "version": "1.0",
        "endpoint": "/api/v1/business/policies/refunds",
        "protocol": "REST",
        "risk_class": "LOW",
        "permission_scope": "policy:read",
        "input_schema": TOOL_SCHEMAS["search_refund_policy"],
        "output_schema": {"type": "object"},
        "enabled": True,
    },
    {
        "id": "issue_refund",
        "name": "issue_refund",
        "version": "1.0",
        "endpoint": "/api/v1/business/refunds",
        "protocol": "REST",
        "risk_class": "HIGH",
        "permission_scope": "refund:write",
        "input_schema": TOOL_SCHEMAS["issue_refund"],
        "output_schema": {"type": "object"},
        "enabled": True,
    },
    {
        "id": "update_shipping",
        "name": "update_shipping",
        "version": "1.0",
        "endpoint": "/api/v1/business/orders/{order_id}/address",
        "protocol": "REST",
        "risk_class": "MEDIUM",
        "permission_scope": "order:write",
        "input_schema": TOOL_SCHEMAS["update_shipping"],
        "output_schema": {"type": "object"},
        "enabled": True,
    },
    {
        "id": "delete_customer",
        "name": "delete_customer",
        "version": "1.0",
        "endpoint": "/api/v1/business/accounts/{customer_id}/disable",
        "protocol": "REST",
        "risk_class": "CRITICAL",
        "permission_scope": "customer:delete",
        "input_schema": TOOL_SCHEMAS["delete_customer"],
        "output_schema": {"type": "object"},
        "enabled": False,
    },
]


def ensure_registry(db: Session) -> None:
    for agent_data in DEFAULT_AGENTS:
        existing = db.query(AgentModel).filter(AgentModel.id == agent_data["id"]).first()
        if not existing:
            db.add(
                AgentModel(
                    id=agent_data["id"],
                    organization_id=DEFAULT_ORG_ID,
                    name=agent_data["name"],
                    owner=agent_data["owner"],
                    version=agent_data["version"],
                    status=agent_data["status"],
                    allowed_tools=agent_data["allowed_tools"],
                    model_provider=agent_data.get("model_provider"),
                    policy_id=agent_data["policy_id"],
                    limits=agent_data["limits"],
                    last_seen=None,
                    created_at=now(),
                    updated_at=now(),
                )
            )
    for tool_data in DEFAULT_TOOLS:
        existing = db.query(ToolModel).filter(ToolModel.id == tool_data["id"]).first()
        if not existing:
            db.add(
                ToolModel(
                    id=tool_data["id"],
                    organization_id=DEFAULT_ORG_ID,
                    name=tool_data["name"],
                    version=tool_data["version"],
                    endpoint=tool_data["endpoint"],
                    protocol=tool_data["protocol"],
                    risk_class=tool_data["risk_class"],
                    permission_scope=tool_data["permission_scope"],
                    input_schema=tool_data["input_schema"],
                    output_schema=tool_data["output_schema"],
                    enabled=tool_data["enabled"],
                    created_at=now(),
                )
            )
    db.commit()


def get_agent(db: Session, agent_id: str) -> AgentModel | None:
    return db.query(AgentModel).filter(AgentModel.id == agent_id).first()


def get_tool(db: Session, tool_id: str) -> ToolModel | None:
    return db.query(ToolModel).filter(ToolModel.id == tool_id).first()


def agent_allows_tool(agent: AgentModel, tool_id: str) -> bool:
    return tool_id in (agent.allowed_tools or [])
