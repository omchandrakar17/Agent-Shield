from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class OrganizationModel(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, default="ACTIVE")
    plan = Column(String, nullable=False, default="standard")
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=True)
    display_name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="ACTIVE")  # ACTIVE, INVITED, DISABLED
    email_verified = Column(Boolean, nullable=False, default=False)
    auth_provider = Column(String, nullable=False, default="local")  # local | firebase
    firebase_uid = Column(String, nullable=True, unique=True)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)


class OrganizationMemberModel(Base):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_user"),)

    id = Column(String, primary_key=True)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String, nullable=False)
    status = Column(String, nullable=False, default="ACTIVE")
    created_at = Column(String, nullable=False)


class InvitationModel(Base):
    __tablename__ = "invitations"

    id = Column(String, primary_key=True)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    email = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False, default="VIEWER")
    token = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, default="PENDING")
    invited_by = Column(String, nullable=False)
    expires_at = Column(String, nullable=False)
    created_at = Column(String, nullable=False)


class PasswordResetModel(Base):
    __tablename__ = "password_resets"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(String, nullable=False)
    used_at = Column(String, nullable=True)
    created_at = Column(String, nullable=False)


class KillSwitchModel(Base):
    __tablename__ = "kill_switches"

    id = Column(String, primary_key=True)
    organization_id = Column(String, nullable=True, index=True)
    scope = Column(String, nullable=False)  # GLOBAL, ORGANIZATION, AGENT, TOOL
    target_id = Column(String, nullable=True)
    enabled = Column(Boolean, nullable=False, default=False)
    reason = Column(Text, nullable=False, default="")
    actor_id = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)


class PolicyModel(Base):
    __tablename__ = "policies"

    id = Column(String, primary_key=True)
    organization_id = Column(String, nullable=False, index=True, default="org-default")
    name = Column(String, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default="PUBLISHED")  # DRAFT, PUBLISHED, ARCHIVED
    published_at = Column(String, nullable=True)
    created_by = Column(String, nullable=False, default="system")
    is_active = Column(Boolean, nullable=False, default=True)
    rules = Column(JSON, nullable=False)
    created_at = Column(String, nullable=False)


class ControlModel(Base):
    __tablename__ = "controls"

    id = Column(String, primary_key=True, default="system_kill_switch")
    enabled = Column(Boolean, nullable=False, default=False)
    reason = Column(Text, nullable=False, default="")
    actor = Column(String, nullable=False, default="system")
    updated_at = Column(String, nullable=False)


class AgentModel(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True)
    organization_id = Column(String, nullable=False, index=True, default="org-default")
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    environment = Column(String, nullable=False, default="production")
    model_provider = Column(String, nullable=True)
    owner = Column(String, nullable=False)
    version = Column(String, nullable=False, default="2026.09.1")
    status = Column(String, nullable=False, default="ACTIVE")  # DRAFT, ACTIVE, PAUSED, DISABLED, ARCHIVED
    allowed_tools = Column(JSON, nullable=False, default=list)
    policy_id = Column(String, nullable=True)
    limits = Column(JSON, nullable=True)
    last_seen = Column(String, nullable=True)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)


class ToolModel(Base):
    __tablename__ = "tools"

    id = Column(String, primary_key=True)
    organization_id = Column(String, nullable=False, index=True, default="org-default")
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    owner = Column(String, nullable=True)
    timeout_seconds = Column(Integer, nullable=False, default=30)
    rate_limit_per_minute = Column(Integer, nullable=True)
    requires_idempotency = Column(Boolean, nullable=False, default=False)
    version = Column(String, nullable=False, default="1.0")
    endpoint = Column(String, nullable=False)
    protocol = Column(String, nullable=False, default="REST")
    risk_class = Column(String, nullable=False, default="LOW")
    permission_scope = Column(String, nullable=False)
    input_schema = Column(JSON, nullable=False)
    output_schema = Column(JSON, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(String, nullable=False)


class ExecutionModel(Base):
    __tablename__ = "executions"

    id = Column(String, primary_key=True)
    organization_id = Column(String, nullable=False, index=True, default="org-default")
    agent_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=False)
    user_request = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="RUNNING", index=True)
    tool_call_count = Column(Integer, nullable=False, default=0)
    tool_call_history = Column(JSON, nullable=True)
    max_tool_calls = Column(Integer, nullable=False, default=12)
    max_execution_seconds = Column(Integer, nullable=False, default=45)
    max_same_tool_repeats = Column(Integer, nullable=False, default=3)
    started_at = Column(String, nullable=False)
    completed_at = Column(String, nullable=True)


class IncidentModel(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True)
    organization_id = Column(String, nullable=False, index=True, default="org-default")
    execution_id = Column(String, nullable=True, index=True)
    action_id = Column(String, nullable=True, index=True)
    incident_type = Column(String, nullable=False, index=True)
    severity = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    reason_codes = Column(JSON, nullable=True)
    status = Column(String, nullable=False, default="OPEN")
    created_at = Column(String, nullable=False, index=True)


class ActionModel(Base):
    __tablename__ = "actions"

    id = Column(String, primary_key=True)
    organization_id = Column(String, nullable=False, index=True, default="org-default")
    execution_id = Column(String, nullable=True, index=True)
    agent_id = Column(String, nullable=False)
    action_type = Column(String, nullable=False)
    target = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    idempotency_key = Column(String, unique=True, index=True, nullable=False)
    fingerprint = Column(String, nullable=False)
    arguments_hash = Column(String, nullable=False)
    status = Column(String, nullable=False, index=True)
    risk_level = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    policy_id = Column(String, nullable=True)
    policy_version = Column(Integer, nullable=True)
    matched_rule_id = Column(String, nullable=True)
    approval_id = Column(String, nullable=True, index=True)
    result = Column(JSON, nullable=True)
    evidence = Column(JSON, nullable=True)
    created_at = Column(String, nullable=False, index=True)
    updated_at = Column(String, nullable=False)
    latency_ms = Column(Float, nullable=True)

    approval = relationship("ApprovalModel", back_populates="action", uselist=False)


class ApprovalModel(Base):
    __tablename__ = "approvals"

    id = Column(String, primary_key=True)
    organization_id = Column(String, nullable=False, index=True, default="org-default")
    action_id = Column(String, ForeignKey("actions.id"), nullable=False, index=True)
    status = Column(String, nullable=False, index=True)
    arguments_hash = Column(String, nullable=False)
    fingerprint = Column(String, nullable=True)  # Composite approval fingerprint
    requested_at = Column(String, nullable=False)
    expires_at = Column(String, nullable=True)
    decided_at = Column(String, nullable=True)
    reviewer = Column(String, nullable=True)
    reason = Column(Text, nullable=True)

    action = relationship("ActionModel", back_populates="approval")


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id = Column(String, primary_key=True)
    organization_id = Column(String, nullable=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    action_id = Column(String, nullable=True, index=True)
    approval_id = Column(String, nullable=True, index=True)
    request_id = Column(String, nullable=True, index=True)
    actor = Column(String, nullable=False, default="system")
    reason_code = Column(String, nullable=True)
    evidence = Column(JSON, nullable=True)
    data = Column(JSON, nullable=True)
    payload_hash = Column(String, nullable=True)
    previous_event_hash = Column(String, nullable=True)
    event_hash = Column(String, nullable=True)
    created_at = Column(String, nullable=False, index=True)


class TraceSpanModel(Base):
    __tablename__ = "trace_spans"

    id = Column(String, primary_key=True)
    action_id = Column(String, nullable=True, index=True)
    execution_id = Column(String, nullable=True, index=True)
    span_name = Column(String, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)
    duration_ms = Column(Float, nullable=False)
    status = Column(String, nullable=False)
    metadata_json = Column(JSON, nullable=True)
