"""Security incidents."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import OperatorContext, OperatorDep
from app.database import get_db
from app.models import IncidentModel
from app.tenant import org_filter

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


@router.get("")
def list_incidents(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    operator: OperatorContext = OperatorDep,
) -> list[dict]:
    incidents = org_filter(db.query(IncidentModel), IncidentModel, operator).order_by(
        IncidentModel.created_at.desc()
    ).limit(limit).all()
    return [{
        "id": i.id, "execution_id": i.execution_id, "action_id": i.action_id,
        "incident_type": i.incident_type, "severity": i.severity,
        "description": i.description, "reason_codes": i.reason_codes,
        "status": i.status, "created_at": i.created_at,
    } for i in incidents]
