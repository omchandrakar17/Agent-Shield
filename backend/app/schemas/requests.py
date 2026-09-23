"""API request/response schemas."""

from pydantic import BaseModel, Field

from app.policy_engine import DEFAULT_POLICY_ID


class ActionRequest(BaseModel):
    agent_id: str = Field(min_length=1)
    action_type: str = Field(min_length=1)
    target: str = Field(min_length=1)
    payload: dict = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1)
    execution_id: str | None = None


class ExecutionStartRequest(BaseModel):
    agent_id: str = Field(min_length=1)
    agent_version: str = Field(default="2026.09.1")
    user_request: str = Field(min_length=1)
    session_id: str = Field(default="sess-demo")


class ExecutionRunRequest(BaseModel):
    user_request: str = Field(min_length=1)


class ToolCallDecisionRequest(BaseModel):
    execution_id: str
    agent_id: str
    agent_version: str = "2026.09.1"
    tool_id: str
    tool_version: str = "1.0"
    arguments: dict = Field(default_factory=dict)
    context: dict = Field(default_factory=dict)
    idempotency_key: str | None = None


class PolicyTestRequest(BaseModel):
    rules: list[dict] = Field(min_length=1)
    action_type: str
    target: str
    payload: dict = Field(default_factory=dict)


class ReplayRequest(BaseModel):
    action_id: str


class AgentCreateRequest(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    version: str = "2026.09.1"
    allowed_tools: list[str] = Field(default_factory=list)
    policy_id: str = DEFAULT_POLICY_ID


class AgentKillSwitchRequest(BaseModel):
    enabled: bool
    reason: str = Field(min_length=1)
    actor: str = Field(min_length=1)


class KillSwitchRequest(BaseModel):
    enabled: bool
    reason: str = Field(min_length=1)
    actor: str = Field(min_length=1)


class ApprovalDecisionRequest(BaseModel):
    decision: str
    reviewer: str = Field(min_length=1)
    reason: str | None = None


class PolicyCreateRequest(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    rules: list[dict] = Field(min_length=1)
    created_by: str = Field(default="admin")


class PolicyUpdateRequest(BaseModel):
    name: str | None = None
    rules: list[dict] | None = None
