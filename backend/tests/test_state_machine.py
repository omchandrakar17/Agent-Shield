from datetime import datetime, timedelta, timezone
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


def test_approval_denial_transitions_to_rejected():
    resp = client.post("/api/v1/actions", json={
        "agent_id": "support-agent",
        "action_type": "issue_refund",
        "target": "order:100",
        "payload": {"amount": 25000, "currency": "INR"},
        "idempotency_key": "deny-key-1",
    })
    approval_id = resp.json()["approval_id"]
    action_id = resp.json()["id"]

    decision_resp = client.post(f"/api/v1/approvals/{approval_id}/decision", json={
        "decision": "denied",
        "reviewer": "compliance_lead",
        "reason": "Suspicious refund pattern",
    })
    assert decision_resp.status_code == 200
    assert decision_resp.json()["approval"]["status"] == "DENIED"
    assert decision_resp.json()["action"]["status"] == "REJECTED"

    # Verify action lookup
    action_check = client.get(f"/api/v1/actions/{action_id}")
    assert action_check.json()["status"] == "REJECTED"
    assert "Suspicious refund" in action_check.json()["reason"]


def test_cannot_decide_already_decided_approval():
    resp = client.post("/api/v1/actions", json={
        "agent_id": "support-agent",
        "action_type": "issue_refund",
        "target": "order:101",
        "payload": {"amount": 25000, "currency": "INR"},
        "idempotency_key": "double-decide-key",
    })
    approval_id = resp.json()["approval_id"]

    first_dec = client.post(f"/api/v1/approvals/{approval_id}/decision", json={
        "decision": "approved",
        "reviewer": "op1",
    })
    assert first_dec.status_code == 200

    second_dec = client.post(f"/api/v1/approvals/{approval_id}/decision", json={
        "decision": "denied",
        "reviewer": "op2",
    })
    assert second_dec.status_code == 409
    assert second_dec.json()["detail"]["code"] == "APPROVAL_ALREADY_DECIDED"


def test_cancel_pending_action():
    resp = client.post("/api/v1/actions", json={
        "agent_id": "support-agent",
        "action_type": "issue_refund",
        "target": "order:102",
        "payload": {"amount": 25000, "currency": "INR"},
        "idempotency_key": "cancel-key",
    })
    action_id = resp.json()["id"]
    approval_id = resp.json()["approval_id"]

    cancel_resp = client.post(f"/api/v1/actions/{action_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    # Check approval is also cancelled
    approvals = client.get(f"/api/v1/approvals?status=CANCELLED").json()
    assert any(a["id"] == approval_id for a in approvals)


def test_pending_action_cannot_approve_after_cancel():
    resp = client.post("/api/v1/actions", json={
        "agent_id": "support-agent",
        "action_type": "issue_refund",
        "target": "order:102b",
        "payload": {"amount": 25000, "currency": "INR"},
        "idempotency_key": "cancel-key-2",
    })
    action_id = resp.json()["id"]
    approval_id = resp.json()["approval_id"]

    # Cancel action
    cancel_resp = client.post(f"/api/v1/actions/{action_id}/cancel")
    assert cancel_resp.status_code == 200

    # Try to approve cancelled action
    decision_resp = client.post(f"/api/v1/approvals/{approval_id}/decision", json={
        "decision": "approved",
        "reviewer": "operator",
    })
    assert decision_resp.status_code == 409
    assert decision_resp.json()["detail"]["code"] == "APPROVAL_ALREADY_DECIDED"


def test_kill_switch_activated_while_approval_pending_blocks_execution():
    resp = client.post("/api/v1/actions", json={
        "agent_id": "support-agent",
        "action_type": "issue_refund",
        "target": "order:103",
        "payload": {"amount": 25000, "currency": "INR"},
        "idempotency_key": "race-key",
    })
    approval_id = resp.json()["approval_id"]
    action_id = resp.json()["id"]

    # Kill switch activated during pending approval!
    client.post("/api/v1/controls/kill-switch", json={
        "enabled": True,
        "reason": "Security emergency",
        "actor": "ciso",
    })

    # Operator tries to approve
    decision_resp = client.post(f"/api/v1/approvals/{approval_id}/decision", json={
        "decision": "approved",
        "reviewer": "operator",
    })
    assert decision_resp.status_code == 200
    assert decision_resp.json()["approval"]["status"] == "BLOCKED"
    assert decision_resp.json()["action"]["status"] == "BLOCKED"
    assert "Kill switch" in decision_resp.json()["action"]["reason"]


def test_approval_binding_detects_mutated_arguments():
    resp = client.post("/api/v1/actions", json={
        "agent_id": "support-agent",
        "action_type": "issue_refund",
        "target": "order:104",
        "payload": {"amount": 25000, "currency": "INR"},
        "idempotency_key": "mutate-key",
    })
    approval_id = resp.json()["approval_id"]
    action_id = resp.json()["id"]

    # Directly mutate action payload in DB to simulate tampering
    db = SessionLocal()
    try:
        act = db.query(ActionModel).filter(ActionModel.id == action_id).first()
        act.payload = {"amount": 999999}  # Tampered amount!
        db.commit()
    finally:
        db.close()

    # Operator tries to approve
    decision_resp = client.post(f"/api/v1/approvals/{approval_id}/decision", json={
        "decision": "approved",
        "reviewer": "operator",
    })
    assert decision_resp.status_code == 409
    assert decision_resp.json()["detail"]["code"] == "ARGUMENT_MISMATCH"


def test_approval_expiration():
    resp = client.post("/api/v1/actions", json={
        "agent_id": "support-agent",
        "action_type": "issue_refund",
        "target": "order:105",
        "payload": {"amount": 25000, "currency": "INR"},
        "idempotency_key": "expire-key",
    })
    approval_id = resp.json()["approval_id"]
    action_id = resp.json()["id"]

    # Manually backdate expires_at to 1 hour ago
    db = SessionLocal()
    try:
        apr = db.query(ApprovalModel).filter(ApprovalModel.id == approval_id).first()
        apr.expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        db.commit()
    finally:
        db.close()

    # Query approvals to trigger auto-expiration
    approvals_resp = client.get("/api/v1/approvals")
    expired = [a for a in approvals_resp.json() if a["id"] == approval_id]
    assert len(expired) == 1
    assert expired[0]["status"] == "EXPIRED"

    # Check action status is also EXPIRED
    act_resp = client.get(f"/api/v1/actions/{action_id}")
    assert act_resp.json()["status"] == "EXPIRED"


def test_expired_approval_rejected_before_execution():
    resp = client.post("/api/v1/actions", json={
        "agent_id": "support-agent",
        "action_type": "issue_refund",
        "target": "order:105b",
        "payload": {"amount": 25000, "currency": "INR"},
        "idempotency_key": "expire-key-2",
    })
    approval_id = resp.json()["approval_id"]

    # Backdate expires_at to 1 hour ago
    db = SessionLocal()
    try:
        apr = db.query(ApprovalModel).filter(ApprovalModel.id == approval_id).first()
        apr.expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        db.commit()
    finally:
        db.close()

    # Attempt to decide expired approval
    decision_resp = client.post(f"/api/v1/approvals/{approval_id}/decision", json={
        "decision": "approved",
        "reviewer": "operator",
    })
    assert decision_resp.status_code == 409
    assert decision_resp.json()["detail"]["code"] == "APPROVAL_EXPIRED"


def test_action_transition_invalid_rejected_state():
    resp = client.post("/api/v1/actions", json={
        "agent_id": "support-agent",
        "action_type": "issue_refund",
        "target": "order:106",
        "payload": {"amount": 25000, "currency": "INR"},
        "idempotency_key": "trans-inv-key",
    })
    action_id = resp.json()["id"]
    approval_id = resp.json()["approval_id"]

    # Reject action
    rej_resp = client.post(f"/api/v1/approvals/{approval_id}/decision", json={
        "decision": "denied",
        "reviewer": "compliance_lead",
    })
    assert rej_resp.status_code == 200

    # Cannot cancel an already rejected action!
    cancel_resp = client.post(f"/api/v1/actions/{action_id}/cancel")
    assert cancel_resp.status_code == 409
    assert cancel_resp.json()["detail"]["code"] == "INVALID_TRANSITION"


def test_policy_publish_is_immutable():
    # 1. Create a draft policy
    create_resp = client.post("/api/v1/policies", json={
        "id": "compliance-policy",
        "name": "Strict Compliance Rules",
        "rules": [
            {"id": "rule-c1", "action": "get_order", "effect": "ALLOW", "risk_level": "LOW", "reason": "Audit read"}
        ],
        "created_by": "sec-team",
    })
    assert create_resp.status_code == 200
    policy_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "DRAFT"

    # 2. Update draft policy
    update_resp = client.put(f"/api/v1/policies/{policy_id}", json={
        "name": "Strict Compliance Rules Updated",
    })
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Strict Compliance Rules Updated"

    # 3. Publish policy
    pub_resp = client.post(f"/api/v1/policies/{policy_id}/publish")
    assert pub_resp.status_code == 200
    assert pub_resp.json()["status"] == "PUBLISHED"

    # 4. Attempt to update published policy -> Fails with 409!
    fail_update = client.put(f"/api/v1/policies/{policy_id}", json={
        "name": "Should fail",
    })
    assert fail_update.status_code == 409
    assert fail_update.json()["detail"]["code"] == "POLICY_VERSION_INVALID"


def test_redaction_in_audit_data():
    resp = client.post(
        "/api/v1/actions",
        json={
            "agent_id": "support-agent",
            "action_type": "get_order",
            "target": "order:999",
            "payload": {
                "api_key": "sensitive_key_9999",
                "secret_token": "bearer_secret_token",
                "auth_header": "Bearer xyz",
            },
            "idempotency_key": "redact-key",
        },
    )
    assert resp.status_code == 200
    action_id = resp.json()["id"]

    audit_resp = client.get(f"/api/v1/audit?action_id={action_id}")
    assert audit_resp.status_code == 200
    events = audit_resp.json()
    assert len(events) >= 1
    data = events[0]["data"]
    # Verify no raw sensitive keys are present in audit payload
    raw_str = str(data)
    assert "sensitive_key_9999" not in raw_str
    assert "bearer_secret_token" not in raw_str


def test_trace_events_are_ordered():
    resp = client.post(
        "/api/v1/actions",
        json={
            "agent_id": "support-agent",
            "action_type": "get_order",
            "target": "order:888",
            "payload": {"include_shipping": True},
            "idempotency_key": "ordered-trace-key",
        },
    )
    assert resp.status_code == 200
    action_id = resp.json()["id"]

    trace_resp = client.get(f"/api/v1/actions/{action_id}/trace")
    assert trace_resp.status_code == 200
    spans = trace_resp.json()["spans"]
    assert len(spans) >= 1
    # Check start times are chronological
    start_times = [s["start_time"] for s in spans]
    assert start_times == sorted(start_times)


def test_idempotency_conflict():
    base = {
        "agent_id": "support-agent",
        "action_type": "get_order",
        "target": "order:777",
        "payload": {"include_shipping": True},
        "idempotency_key": "same-key-1",
    }
    r1 = client.post("/api/v1/actions", json=base)
    assert r1.status_code == 200

    # Repeat exact same payload -> returns same action
    r2 = client.post("/api/v1/actions", json=base)
    assert r2.status_code == 200
    assert r2.json()["id"] == r1.json()["id"]

    # Same key with different payload -> 409 conflict
    mutated = dict(base)
    mutated["payload"] = {"include_shipping": False}
    r3 = client.post("/api/v1/actions", json=mutated)
    assert r3.status_code == 409
    assert r3.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"
