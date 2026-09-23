"""Analytics API — dashboard metrics from persisted data only."""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import OperatorDep, require_permission
from app.auth import OperatorContext
from app.core.rbac import Permission
from app.database import get_db
from app.models import ActionModel, AgentModel, ApprovalModel, ExecutionModel, IncidentModel
from app.policy_engine import ActionStatus
from app.tenant import org_filter

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/dashboard")
def dashboard_summary(
    operator: OperatorContext = Depends(require_permission(Permission.ANALYTICS_READ)),
    db: Session = Depends(get_db),
) -> dict:
    org_id = operator.organization_id

    active_agents = (
        org_filter(db.query(AgentModel), AgentModel, operator)
        .filter(AgentModel.status == "ACTIVE")
        .count()
    )

    actions_q = org_filter(db.query(ActionModel), ActionModel, operator)
    protected_calls = actions_q.count()
    blocked_actions = actions_q.filter(ActionModel.status == ActionStatus.blocked.value).count()

    pending_approvals = (
        org_filter(db.query(ApprovalModel), ApprovalModel, operator)
        .filter(ApprovalModel.status == "PENDING")
        .count()
    )

    security_events = (
        org_filter(db.query(IncidentModel), IncidentModel, operator)
        .filter(IncidentModel.status == "OPEN")
        .count()
    )

    executions_q = org_filter(db.query(ExecutionModel), ExecutionModel, operator)
    total_executions = executions_q.count()
    completed = executions_q.filter(ExecutionModel.status.in_(["COMPLETED", "FAILED", "BLOCKED"])).count()
    successful = executions_q.filter(ExecutionModel.status == "COMPLETED").count()

    success_rate = round((successful / completed) * 100, 1) if completed else None

    avg_latency = (
        org_filter(db.query(ActionModel), ActionModel, operator)
        .filter(ActionModel.latency_ms.isnot(None))
        .with_entities(func.avg(ActionModel.latency_ms))
        .scalar()
    )

    return {
        "active_agents": active_agents,
        "protected_tool_calls": protected_calls,
        "blocked_actions": blocked_actions,
        "pending_approvals": pending_approvals,
        "security_events": security_events,
        "execution_success_rate": success_rate,
        "average_decision_time_ms": round(avg_latency, 1) if avg_latency else None,
        "has_data": protected_calls > 0 or total_executions > 0,
    }
