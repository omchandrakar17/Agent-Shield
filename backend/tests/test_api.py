from fastapi.testclient import TestClient
import pytest
from app.main import app
from app.database import SessionLocal, init_db
from app.models import (
    ActionModel, AgentModel, ApprovalModel, AuditEventModel, ControlModel,
    ExecutionModel, IncidentModel, PolicyModel, ToolModel, TraceSpanModel,
)
from app.registry import ensure_registry

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    init_db()
    db = SessionLocal()
    try:
        db.query(IncidentModel).delete()
        db.query(TraceSpanModel).delete()
        db.query(AuditEventModel).delete()
        db.query(ApprovalModel).delete()
        db.query(ActionModel).delete()
        db.query(ExecutionModel).delete()
        db.query(AgentModel).delete()
        db.query(ToolModel).delete()
        db.query(PolicyModel).delete()
        from app.policy_engine import ensure_default_policy
        ensure_default_policy(db)
        ensure_registry(db)
        ctrl = db.query(ControlModel).filter(ControlModel.id == "system_kill_switch").first()
        if ctrl:
            ctrl.enabled = False
            ctrl.reason = ""
            ctrl.actor = "system"
        db.commit()
    finally:
        db.close()


def payload(action_type: str, key: str, amount: int | None = None):
    return {
        "agent_id": "support-agent",
        "action_type": action_type,
        "target": "order:2481",
        "payload": {} if amount is None else {"amount": amount, "currency": "INR"},
        "idempotency_key": key,
    }


def test_safe_read_executes():
    response = client.post("/api/v1/actions", json=payload("get_order", "read-1"))
    assert response.status_code == 200
    assert response.json()["status"] == "EXECUTED"


def test_refund_requires_and_then_accepts_approval():
    response = client.post("/api/v1/actions", json=payload("issue_refund", "refund-1", 25000))
    assert response.status_code == 200
    approval_id = response.json()["approval_id"]
    assert response.json()["status"] == "REQUIRE_APPROVAL"
    decision = client.post(f"/api/v1/approvals/{approval_id}/decision", json={"decision": "approved", "reviewer": "operator"})
    assert decision.status_code == 200
    assert decision.json()["action"]["status"] == "EXECUTED"


def test_unknown_action_is_blocked():
    response = client.post("/api/v1/actions", json=payload("send_money", "unknown-1"))
    assert response.json()["status"] == "BLOCKED"


def test_kill_switch_blocks_new_actions():
    client.post("/api/v1/controls/kill-switch", json={"enabled": True, "reason": "incident", "actor": "operator"})
    response = client.post("/api/v1/actions", json=payload("get_order", "blocked-1"))
    assert response.status_code == 423
