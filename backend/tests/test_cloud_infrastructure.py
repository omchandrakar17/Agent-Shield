"""Cloud infrastructure module tests (no live GCP required)."""

import os

import pytest

from app.cloud.adapters import CompositeEventSink, GcpPubSubSink, LocalEventSink
from app.cloud.bigquery_client import BigQueryAnalytics
from app.cloud.bootstrap import SECRET_BINDINGS, load_secrets_from_manager
from app.cloud.firestore_store import FirestoreStore
from app.core.config import get_settings


def test_composite_event_sink_fanout():
    local = LocalEventSink(max_buffer=10)
    composite = CompositeEventSink([local])
    composite.publish_event("test", {"x": 1})
    composite.publish_audit({"id": "a1", "event_type": "ACTION_DECISION"})
    assert len(local.events) >= 1


def test_pubsub_sink_simulated_mode():
    sink = GcpPubSubSink(project_id="test-project", topic_id="events")
    sink.publish_audit({"id": "audit-1", "event_type": "ACTION_DECISION"})
    sink.publish_event("action.created", {"id": "act-1"})


def test_firestore_store_simulated_mode():
    store = FirestoreStore(project_id="test-project")
    assert store.available is False
    assert store.write_audit_event({"id": "e1", "event_type": "TEST"}) is False


def test_bigquery_simulated_mode():
    bq = BigQueryAnalytics(project_id="test-project", dataset_id="agentshield")
    assert bq.available is False
    assert bq.insert_audit_row({"id": "e1", "event_type": "TEST"}) is False


def test_secret_bindings_defined():
    assert "AGENTSHIELD_JWT_SECRET" in SECRET_BINDINGS
    assert "AGENTSHIELD_AGENT_API_KEY" in SECRET_BINDINGS


def test_load_secrets_skipped_when_disabled():
    os.environ["AGENTSHIELD_USE_SECRET_MANAGER"] = "false"
    get_settings.cache_clear()
    load_secrets_from_manager()
    get_settings.cache_clear()
