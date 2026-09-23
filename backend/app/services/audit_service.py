"""Tamper-evident audit log."""

from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.events import event_sink, publish_event
from app.models import ActionModel, AuditEventModel
from app.security import canonical_hash, now, redact_data


def record_audit(
    db: Session,
    event_type: str,
    action_id: str | None,
    approval_id: str | None,
    request_id: str,
    actor: str,
    data: dict,
    reason_code: str | None = None,
    evidence: dict | None = None,
    organization_id: str | None = None,
) -> AuditEventModel:
    if organization_id is None and action_id:
        linked = db.query(ActionModel).filter(ActionModel.id == action_id).first()
        if linked:
            organization_id = linked.organization_id

    sanitized_data = redact_data(data)
    sanitized_evidence = redact_data(evidence) if evidence else None

    last_evt = db.query(AuditEventModel).order_by(AuditEventModel.created_at.desc()).first()
    previous_hash = last_evt.event_hash if last_evt and last_evt.event_hash else "sha256:genesis"

    payload_body = {
        "event_type": event_type,
        "action_id": action_id,
        "approval_id": approval_id,
        "request_id": request_id,
        "actor": actor,
        "data": sanitized_data,
        "previous_event_hash": previous_hash,
    }
    payload_hash = canonical_hash(payload_body)
    event_hash = canonical_hash({**payload_body, "payload_hash": payload_hash})

    evt = AuditEventModel(
        id=str(uuid4()),
        organization_id=organization_id,
        event_type=event_type,
        action_id=action_id,
        approval_id=approval_id,
        request_id=request_id,
        actor=actor,
        reason_code=reason_code,
        data=sanitized_data,
        evidence=sanitized_evidence,
        payload_hash=payload_hash,
        previous_event_hash=previous_hash,
        event_hash=event_hash,
        created_at=now(),
    )
    db.add(evt)
    db.commit()
    audit_payload = {
        "id": evt.id,
        "organization_id": organization_id,
        "event_type": evt.event_type,
        "action_id": evt.action_id,
        "approval_id": evt.approval_id,
        "request_id": evt.request_id,
        "actor": evt.actor,
        "created_at": evt.created_at,
        "data": evt.data,
        "payload_hash": evt.payload_hash,
        "previous_event_hash": evt.previous_event_hash,
        "event_hash": evt.event_hash,
    }
    publish_event("audit.created", audit_payload)
    event_sink.publish_audit(audit_payload)

    from app.cloud.bigquery_client import get_bigquery_client
    from app.cloud.firestore_store import get_firestore_store

    fs = get_firestore_store()
    if fs:
        fs.write_audit_event(audit_payload)
    bq = get_bigquery_client()
    if bq:
        bq.insert_audit_row(audit_payload)

    return evt
