"""Security incident persistence."""

from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.events import publish_event
from app.models import IncidentModel
from app.security import now


def create_incident(
    db: Session,
    incident_type: str,
    severity: str,
    description: str,
    reason_codes: list[str],
    execution_id: str | None = None,
    action_id: str | None = None,
    organization_id: str | None = None,
) -> IncidentModel:
    incident = IncidentModel(
        id="inc-" + uuid4().hex[:10],
        organization_id=organization_id or "org-default",
        execution_id=execution_id,
        action_id=action_id,
        incident_type=incident_type,
        severity=severity,
        description=description,
        reason_codes=reason_codes,
        status="OPEN",
        created_at=now(),
    )
    db.add(incident)
    db.commit()
    incident_payload = {
        "id": incident.id,
        "organization_id": incident.organization_id,
        "execution_id": execution_id,
        "action_id": action_id,
        "incident_type": incident_type,
        "severity": severity,
        "description": description,
        "reason_codes": reason_codes,
        "status": "OPEN",
        "created_at": incident.created_at,
    }
    publish_event("incident.created", incident_payload)

    from app.cloud.firestore_store import get_firestore_store

    fs = get_firestore_store()
    if fs:
        fs.write_security_event(incident_payload)

    return incident
