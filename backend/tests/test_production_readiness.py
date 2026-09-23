"""Production deployment readiness tests."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models import ControlModel, KillSwitchModel
from app.runtime.rate_limit import reset_rate_limits
from app.services.bootstrap import should_seed_users

client = TestClient(app)


@pytest.fixture(autouse=True)
def production_readiness_env():
    os.environ["AGENTSHIELD_ENV"] = "development"
    os.environ.pop("AGENTSHIELD_AGENT_API_KEY", None)
    get_settings.cache_clear()
    reset_rate_limits()
    db = SessionLocal()
    try:
        db.query(KillSwitchModel).delete()
        ctrl = db.query(ControlModel).filter(ControlModel.id == "system_kill_switch").first()
        if ctrl:
            ctrl.enabled = False
        db.commit()
    finally:
        db.close()
    yield
    get_settings.cache_clear()


def test_should_not_seed_users_in_production_by_default():
    os.environ["AGENTSHIELD_ENV"] = "production"
    os.environ.pop("AGENTSHIELD_SEED_USERS", None)
    get_settings.cache_clear()
    assert should_seed_users() is False
    os.environ["AGENTSHIELD_ENV"] = "development"
    get_settings.cache_clear()


def test_healthz_alias():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_runtime_smoke_read_action_without_api_key_in_dev():
    os.environ["AGENTSHIELD_ENV"] = "development"
    os.environ.pop("AGENTSHIELD_AGENT_API_KEY", None)
    get_settings.cache_clear()
    response = client.post(
        "/api/v1/actions",
        json={
            "agent_id": "support-agent",
            "action_type": "get_order",
            "target": "order:2481",
            "payload": {"include_shipping": True},
            "idempotency_key": f"prod-readiness-{uuid4().hex[:8]}",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] in {"EXECUTED", "ALLOWED"}


def test_production_runtime_requires_api_key():
    os.environ["AGENTSHIELD_ENV"] = "production"
    os.environ.pop("AGENTSHIELD_AGENT_API_KEY", None)
    get_settings.cache_clear()
    response = client.post(
        "/api/v1/actions",
        json={
            "agent_id": "support-agent",
            "action_type": "get_order",
            "target": "order:2481",
            "payload": {},
            "idempotency_key": "prod-guard-1",
        },
    )
    assert response.status_code == 503
    os.environ["AGENTSHIELD_ENV"] = "development"
    get_settings.cache_clear()
