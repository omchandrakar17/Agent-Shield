"""Runtime gateway hardening tests."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.database import SessionLocal, init_db
from app.models import AgentModel, ControlModel, KillSwitchModel, ToolModel
from app.policy_engine import ensure_default_policy
from app.registry import ensure_registry
from app.runtime.rate_limit import reset_rate_limits
from app.security import now

client = TestClient(app)


@pytest.fixture(autouse=True)
def runtime_env():
    os.environ.pop("AGENTSHIELD_AGENT_API_KEY", None)
    os.environ.pop("AGENTSHIELD_INTERNAL_SERVICE_KEY", None)
    get_settings.cache_clear()
    reset_rate_limits()
    init_db()
    db = SessionLocal()
    try:
        from app.models import ActionModel, ApprovalModel, AuditEventModel, ExecutionModel, IncidentModel, TraceSpanModel

        db.query(IncidentModel).delete()
        db.query(TraceSpanModel).delete()
        db.query(AuditEventModel).delete()
        db.query(ApprovalModel).delete()
        db.query(ActionModel).delete()
        db.query(ExecutionModel).delete()
        db.query(KillSwitchModel).delete()
        ensure_default_policy(db)
        ensure_registry(db)
        ctrl = db.query(ControlModel).filter(ControlModel.id == "system_kill_switch").first()
        if ctrl:
            ctrl.enabled = False
        db.commit()
    finally:
        db.close()
    yield
    get_settings.cache_clear()


def _action_payload(key: str, action_type: str = "get_order", amount: int | None = None):
    return {
        "agent_id": "support-agent",
        "action_type": action_type,
        "target": "order:2481",
        "payload": {} if amount is None else {"amount": amount, "currency": "INR", "order_id": "2481"},
        "idempotency_key": key,
    }


def test_runtime_api_key_required_when_configured():
    os.environ["AGENTSHIELD_AGENT_API_KEY"] = "test-runtime-key"
    get_settings.cache_clear()
    response = client.post("/api/v1/actions", json=_action_payload("key-auth-1"))
    assert response.status_code == 401
    authed = client.post(
        "/api/v1/actions",
        json=_action_payload("key-auth-2"),
        headers={"X-Agent-Api-Key": "test-runtime-key"},
    )
    assert authed.status_code == 200


def test_business_api_blocks_direct_access_when_internal_key_set():
    os.environ["AGENTSHIELD_INTERNAL_SERVICE_KEY"] = "internal-only"
    get_settings.cache_clear()
    blocked = client.get("/api/v1/business/orders/2481")
    assert blocked.status_code == 403
    allowed = client.get(
        "/api/v1/business/orders/2481",
        headers={"X-Internal-Service-Key": "internal-only"},
    )
    assert allowed.status_code == 200


def test_scoped_agent_kill_switch_blocks_runtime():
    db = SessionLocal()
    try:
        db.add(
            KillSwitchModel(
                id=f"ks-{uuid4().hex[:8]}",
                organization_id="org-default",
                scope="AGENT",
                target_id="support-agent",
                enabled=True,
                reason="agent suspended",
                actor_id="test",
                updated_at=now(),
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.post("/api/v1/actions", json=_action_payload("agent-ks-1"))
    assert response.status_code == 423


def test_organization_id_set_on_action():
    response = client.post("/api/v1/actions", json=_action_payload("org-id-1"))
    assert response.status_code == 200
    db = SessionLocal()
    try:
        from app.models import ActionModel

        action = db.query(ActionModel).filter(ActionModel.idempotency_key == "org-id-1").first()
        assert action is not None
        assert action.organization_id == "org-default"
    finally:
        db.close()


def test_rate_limit_blocks_excessive_calls():
    db = SessionLocal()
    try:
        tool = db.query(ToolModel).filter(ToolModel.id == "get_order").first()
        tool.rate_limit_per_minute = 2
        db.commit()
    finally:
        db.close()

    assert client.post("/api/v1/actions", json=_action_payload("rate-1")).status_code == 200
    assert client.post("/api/v1/actions", json=_action_payload("rate-2")).status_code == 200
    blocked = client.post("/api/v1/actions", json=_action_payload("rate-3"))
    assert blocked.status_code == 429
