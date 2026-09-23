import os
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, DATABASE_URL, SessionLocal, init_db
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


def test_restart_persistence():
    # 1. Submit an action through the API
    payload = {
        "agent_id": "support-agent",
        "action_type": "issue_refund",
        "target": "order:8899",
        "payload": {"amount": 15000, "currency": "INR"},
        "idempotency_key": "persist-key-1",
    }
    resp = client.post("/api/v1/actions", json=payload)
    assert resp.status_code == 200
    action_data = resp.json()
    action_id = action_data["id"]
    approval_id = action_data["approval_id"]
    assert approval_id is not None

    # Update kill switch
    ctrl_resp = client.post("/api/v1/controls/kill-switch", json={
        "enabled": True,
        "reason": "Maintenance reboot",
        "actor": "admin",
    })
    assert ctrl_resp.status_code == 200

    # 2. Simulate restarting the process by opening a completely separate engine/session to the SQLite DB
    direct_engine = create_engine(DATABASE_URL)
    DirectSession = sessionmaker(bind=direct_engine)
    session = DirectSession()
    try:
        # Check action in DB
        db_action = session.query(ActionModel).filter(ActionModel.id == action_id).first()
        assert db_action is not None
        assert db_action.action_type == "issue_refund"
        assert db_action.target == "order:8899"
        assert db_action.payload["amount"] == 15000
        assert db_action.status == "REQUIRE_APPROVAL"

        # Check approval in DB
        db_approval = session.query(ApprovalModel).filter(ApprovalModel.id == approval_id).first()
        assert db_approval is not None
        assert db_approval.action_id == action_id
        assert db_approval.status == "PENDING"
        assert db_approval.arguments_hash == db_action.arguments_hash

        # Check kill switch in DB
        db_ctrl = session.query(ControlModel).filter(ControlModel.id == "system_kill_switch").first()
        assert db_ctrl is not None
        assert db_ctrl.enabled is True
        assert db_ctrl.reason == "Maintenance reboot"

        # Check audit event in DB
        audit_events = session.query(AuditEventModel).filter(AuditEventModel.action_id == action_id).all()
        assert len(audit_events) >= 1
        assert any(e.event_type == "ACTION_DECISION" for e in audit_events)
    finally:
        session.close()
        direct_engine.dispose()

