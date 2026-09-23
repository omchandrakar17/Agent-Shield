"""Security regression tests — auth, tenant isolation, RBAC, audit chain."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth import create_access_token
from app.core.config import get_settings
from app.core.rbac import Role
from app.database import SessionLocal, init_db
from app.main import app
from app.models import AgentModel, AuditEventModel
from app.policy_engine import ensure_default_policy
from app.registry import ensure_registry
from app.security import now
from app.services.audit_chain import verify_audit_chain
from app.services.audit_service import record_audit


@pytest.fixture(autouse=True)
def local_auth_mode():
    os.environ["AGENTSHIELD_AUTH_MODE"] = "local"
    os.environ["AGENTSHIELD_ENV"] = "development"
    os.environ.pop("AGENTSHIELD_AGENT_API_KEY", None)
    os.environ.pop("AGENTSHIELD_INTERNAL_SERVICE_KEY", None)
    get_settings.cache_clear()
    init_db()
    db = SessionLocal()
    try:
        ensure_default_policy(db)
        ensure_registry(db)
        db.commit()
    finally:
        db.close()
    yield
    os.environ["AGENTSHIELD_AUTH_MODE"] = "disabled"
    os.environ["AGENTSHIELD_ENV"] = "development"
    get_settings.cache_clear()


client = TestClient(app)


def _register_org(name: str) -> tuple[str, str, str]:
    email = f"sec-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": name,
            "email": email,
            "password": "securepass123",
            "display_name": "Security Tester",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return body["access_token"], body["user"]["organization_id"], email


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_operator_routes_require_auth_in_local_mode():
    response = client.get("/api/v1/agents")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_REQUIRED"


def test_invalid_jwt_rejected():
    response = client.get("/api/v1/agents", headers=_auth_headers("not-a-valid-token"))
    assert response.status_code == 401


def test_tenant_isolation_on_agent_list():
    default_login = client.post(
        "/api/v1/auth/login",
        json={"email": "operator@agentshield.example", "password": "agentshield2026"},
    )
    assert default_login.status_code == 200
    default_token = default_login.json()["access_token"]

    other_token, other_org_id, _ = _register_org("Isolated Tenant Corp")

    default_agents = client.get("/api/v1/agents", headers=_auth_headers(default_token))
    other_agents = client.get("/api/v1/agents", headers=_auth_headers(other_token))

    assert default_agents.status_code == 200
    assert other_agents.status_code == 200

    default_ids = {a["id"] for a in default_agents.json()}
    other_ids = {a["id"] for a in other_agents.json()}

    assert "support-agent" in default_ids
    assert "support-agent" not in other_ids

    agent_id = f"tenant-agent-{uuid4().hex[:6]}"
    created = client.post(
        "/api/v1/agents",
        headers=_auth_headers(other_token),
        json={
            "id": agent_id,
            "name": "Tenant Agent",
            "owner": "security-test",
            "version": "1.0.0",
            "allowed_tools": ["get_order"],
            "policy_id": "default-policy",
        },
    )
    assert created.status_code == 200

    cross_tenant = client.get(f"/api/v1/agents/{agent_id}", headers=_auth_headers(default_token))
    assert cross_tenant.status_code == 404

    own_agent = client.get(f"/api/v1/agents/{agent_id}", headers=_auth_headers(other_token))
    assert own_agent.status_code == 200
    assert own_agent.json()["id"] == agent_id

    db = SessionLocal()
    try:
        row = db.query(AgentModel).filter(AgentModel.id == agent_id).first()
        assert row is not None
        assert row.organization_id == other_org_id
    finally:
        db.close()


def test_viewer_role_cannot_manage_kill_switches():
    owner_token, org_id, _ = _register_org("RBAC Kill Switch Org")

    viewer_token = create_access_token(
        user_id=f"viewer-{uuid4().hex[:6]}",
        email=f"viewer-{uuid4().hex[:6]}@example.com",
        role=Role.VIEWER.value,
        display_name="Viewer User",
        organization_id=org_id,
    )

    denied = client.get("/api/v1/kill-switches", headers=_auth_headers(viewer_token))
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "FORBIDDEN"

    allowed = client.get("/api/v1/kill-switches", headers=_auth_headers(owner_token))
    assert allowed.status_code == 200


def test_audit_hash_chain_integrity():
    db = SessionLocal()
    try:
        for idx in range(3):
            record_audit(
                db=db,
                event_type="SECURITY_TEST",
                action_id=None,
                approval_id=None,
                request_id=f"req-{idx}",
                actor="security-test",
                data={"sequence": idx},
                organization_id="org-default",
            )

        valid, message = verify_audit_chain(db, organization_id="org-default")
        assert valid, message

        target = (
            db.query(AuditEventModel)
            .filter(AuditEventModel.organization_id == "org-default")
            .order_by(AuditEventModel.created_at.desc())
            .first()
        )
        assert target is not None
        target.data = {"tampered": True}
        db.commit()

        valid_after_tamper, tamper_message = verify_audit_chain(db, organization_id="org-default")
        assert not valid_after_tamper
        assert "tamper" in tamper_message
    finally:
        db.close()


def test_production_requires_runtime_api_key():
    os.environ["AGENTSHIELD_ENV"] = "production"
    get_settings.cache_clear()

    response = client.post(
        "/api/v1/actions",
        json={
            "agent_id": "support-agent",
            "action_type": "get_order",
            "target": "order:2481",
            "payload": {},
            "idempotency_key": f"prod-auth-{uuid4().hex[:6]}",
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "RUNTIME_AUTH_NOT_CONFIGURED"
