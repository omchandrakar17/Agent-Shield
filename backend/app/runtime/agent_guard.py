"""Agent lifecycle and execution binding guards."""

from sqlalchemy.orm import Session

from app.models import AgentModel, ExecutionModel

NON_EXECUTABLE_STATUSES = frozenset({"DISABLED", "PAUSED", "ARCHIVED", "DRAFT"})


def assert_agent_executable(agent: AgentModel) -> tuple[bool, str, str]:
    if agent.status in NON_EXECUTABLE_STATUSES:
        return False, "AGENT_NOT_EXECUTABLE", f"Agent '{agent.id}' is {agent.status} and cannot execute tools"
    return True, "", ""


def resolve_organization_id(agent: AgentModel) -> str:
    return agent.organization_id or "org-default"


def assert_execution_binding(db: Session, execution_id: str | None, agent_id: str) -> ExecutionModel | None:
    if not execution_id:
        return None
    execution = db.query(ExecutionModel).filter(ExecutionModel.id == execution_id).first()
    if not execution:
        return None
    if execution.agent_id != agent_id:
        raise ValueError("EXECUTION_AGENT_MISMATCH")
    return execution
