"""Audit hash-chain verification."""

from sqlalchemy.orm import Session

from app.models import AuditEventModel
from app.security import canonical_hash


def verify_audit_chain(db: Session, organization_id: str | None = None) -> tuple[bool, str]:
    """Verify tamper-evident audit event hash chain for an organization."""
    query = db.query(AuditEventModel).order_by(AuditEventModel.created_at.asc())
    if organization_id:
        query = query.filter(AuditEventModel.organization_id == organization_id)

    events = query.all()
    expected_previous = "sha256:genesis"

    for evt in events:
        if evt.previous_event_hash != expected_previous:
            return False, f"chain break at event {evt.id}"

        payload_body = {
            "event_type": evt.event_type,
            "action_id": evt.action_id,
            "approval_id": evt.approval_id,
            "request_id": evt.request_id,
            "actor": evt.actor,
            "data": evt.data,
            "previous_event_hash": evt.previous_event_hash,
        }
        payload_hash = canonical_hash(payload_body)
        if evt.payload_hash != payload_hash:
            return False, f"payload tamper at event {evt.id}"

        event_hash = canonical_hash({**payload_body, "payload_hash": payload_hash})
        if evt.event_hash != event_hash:
            return False, f"hash tamper at event {evt.id}"

        expected_previous = evt.event_hash

    return True, "ok"
