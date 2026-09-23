"""Google Cloud Firestore — operational document mirror for audit and security events."""

import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger("agentshield.cloud.firestore")

_store: "FirestoreStore | None" = None


class FirestoreStore:
    """Writes append-only documents to Firestore collections (mirror of SQL audit/incidents)."""

    def __init__(self, project_id: str, database_id: str = "(default)") -> None:
        self.project_id = project_id
        self.database_id = database_id
        self._client = None
        try:
            from google.cloud import firestore  # type: ignore

            self._client = firestore.Client(project=project_id, database=database_id)
            logger.info("Firestore client initialized for project %s", project_id)
        except ImportError:
            logger.warning("google-cloud-firestore not installed — Firestore mirror disabled")
        except Exception as exc:
            logger.warning("Firestore client init failed: %s", exc)

    @property
    def available(self) -> bool:
        return self._client is not None

    def write_document(self, collection: str, document_id: str, data: dict[str, Any]) -> bool:
        if not self._client:
            logger.debug("[SIMULATED FIRESTORE] %s/%s", collection, document_id)
            return False
        try:
            self._client.collection(collection).document(document_id).set(data)
            return True
        except Exception as exc:
            logger.error("Firestore write failed %s/%s: %s", collection, document_id, exc)
            return False

    def write_audit_event(self, audit_event: dict[str, Any]) -> bool:
        doc_id = audit_event.get("id") or audit_event.get("event_type", "unknown")
        payload = {
            **audit_event,
            "organization_id": audit_event.get("organization_id"),
            "sink": "firestore_mirror",
        }
        return self.write_document("audit_events", str(doc_id), payload)

    def write_security_event(self, incident: dict[str, Any]) -> bool:
        doc_id = incident.get("id", "incident")
        return self.write_document("security_events", str(doc_id), incident)


def get_firestore_store() -> FirestoreStore | None:
    global _store
    if _store is not None:
        return _store

    settings = get_settings()
    if not settings.use_firestore or not settings.firestore_project_id:
        return None

    store = FirestoreStore(
        project_id=settings.firestore_project_id,
        database_id=settings.firestore_database_id,
    )
    _store = store if store.available else None
    return _store
