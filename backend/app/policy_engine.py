from enum import Enum
from typing import Any
from sqlalchemy.orm import Session
from app.models import PolicyModel
from app.security import now


class ActionStatus(str, Enum):
    submitted = "SUBMITTED"
    executed = "EXECUTED"
    awaiting_approval = "REQUIRE_APPROVAL"
    approved = "APPROVED"
    rejected = "REJECTED"
    expired = "EXPIRED"
    cancelled = "CANCELLED"
    blocked = "BLOCKED"
    failed = "FAILED"


DEFAULT_POLICY_ID = "default-policy"
DEFAULT_RULES = [
    {
        "id": "rule-read-order",
        "action": "get_order",
        "target_prefix": "order:",
        "effect": "ALLOW",
        "risk_level": "LOW",
        "reason": "Read-only sandbox lookup",
    },
    {
        "id": "rule-read-customer",
        "action": "get_customer",
        "target_prefix": "customer:",
        "effect": "ALLOW",
        "risk_level": "LOW",
        "reason": "Read-only customer lookup",
    },
    {
        "id": "rule-search-policy",
        "action": "search_refund_policy",
        "effect": "ALLOW",
        "risk_level": "LOW",
        "reason": "Policy retrieval is read-only",
    },
    {
        "id": "rule-refund-low",
        "action": "issue_refund",
        "target_prefix": "order:",
        "effect": "ALLOW",
        "risk_level": "MEDIUM",
        "reason": "Refund within autonomous limit (≤ ₹10,000)",
        "when": {"amount": {"lte": 10000}},
        "validation": {"require_positive_amount": True},
    },
    {
        "id": "rule-refund-high",
        "action": "issue_refund",
        "target_prefix": "order:",
        "effect": "REQUIRE_APPROVAL",
        "risk_level": "HIGH",
        "reason": "Refund exceeds autonomous limit (> ₹10,000)",
        "when": {"amount": {"gt": 10000}},
        "validation": {"require_positive_amount": True},
    },
    {
        "id": "rule-update-shipping",
        "action": "update_shipping",
        "target_prefix": "order:",
        "effect": "REQUIRE_APPROVAL",
        "risk_level": "MEDIUM",
        "reason": "Address mutation requires approval",
    },
    {
        "id": "rule-delete-customer",
        "action": "delete_customer",
        "effect": "BLOCK",
        "risk_level": "CRITICAL",
        "reason": "Critical destructive tool is disabled in the demo",
    },
]


def ensure_default_policy(db: Session) -> PolicyModel:
    policy = db.query(PolicyModel).filter(
        PolicyModel.id == DEFAULT_POLICY_ID,
        PolicyModel.status == "PUBLISHED"
    ).first()
    if not policy:
        policy = PolicyModel(
            id=DEFAULT_POLICY_ID,
            organization_id="org-default",
            name="Default Agent Guardrail Policy",
            version=1,
            status="PUBLISHED",
            published_at=now(),
            created_by="system",
            is_active=True,
            rules=DEFAULT_RULES,
            created_at=now(),
        )
        db.add(policy)
        db.commit()
        db.refresh(policy)
    return policy


def _matches_when(when: dict[str, Any], payload: dict[str, Any]) -> bool:
    if not when:
        return True
    for field, constraints in when.items():
        value = payload.get(field)
        if isinstance(constraints, dict):
            if "gt" in constraints and not (isinstance(value, (int, float)) and value > constraints["gt"]):
                return False
            if "gte" in constraints and not (isinstance(value, (int, float)) and value >= constraints["gte"]):
                return False
            if "lt" in constraints and not (isinstance(value, (int, float)) and value < constraints["lt"]):
                return False
            if "lte" in constraints and not (isinstance(value, (int, float)) and value <= constraints["lte"]):
                return False
            if "eq" in constraints and value != constraints["eq"]:
                return False
        elif value != constraints:
            return False
    return True


def evaluate_action(
    action_type: str,
    target: str,
    payload: dict[str, Any],
    db: Session,
) -> tuple[ActionStatus, str, str, str, int, str]:
    """
    Evaluates action against the active PUBLISHED policy.
    Returns: (status, risk_level, reason, policy_id, policy_version, matched_rule_id)
    """
    policy = (
        db.query(PolicyModel)
        .filter(PolicyModel.is_active == True, PolicyModel.status == "PUBLISHED")  # noqa: E712
        .order_by(PolicyModel.version.desc())
        .first()
    )
    if not policy:
        policy = ensure_default_policy(db)

    matched_rules = []
    for rule in policy.rules:
        if rule.get("action") != action_type:
            continue
        target_prefix = rule.get("target_prefix")
        if target_prefix and not target.startswith(target_prefix):
            continue
        when = rule.get("when")
        if when and not _matches_when(when, payload):
            continue
        matched_rules.append(rule)

    for rule in matched_rules:
        rule_id = rule.get("id", "rule-custom")

        if action_type == "issue_refund":
            amount = payload.get("amount")
            if not isinstance(amount, (int, float)) or amount <= 0:
                return (
                    ActionStatus.blocked,
                    "HIGH",
                    "Refund amount must be a positive number",
                    policy.id,
                    policy.version,
                    rule_id,
                )

        effect = rule.get("effect")
        risk = rule.get("risk_level", "HIGH")
        reason = rule.get("reason", "Guardrail rule matched")

        if effect == "ALLOW":
            return ActionStatus.executed, risk, reason, policy.id, policy.version, rule_id
        elif effect == "REQUIRE_APPROVAL":
            return ActionStatus.awaiting_approval, risk, reason, policy.id, policy.version, rule_id
        elif effect == "BLOCK":
            return ActionStatus.blocked, risk, reason, policy.id, policy.version, rule_id

    return (
        ActionStatus.blocked,
        "HIGH",
        "Action is not registered in active policy",
        policy.id,
        policy.version,
        "rule-default-deny",
    )


def test_policy_rules(
    rules: list[dict],
    action_type: str,
    target: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate proposed rules without persisting."""
    for rule in rules:
        if rule.get("action") != action_type:
            continue
        target_prefix = rule.get("target_prefix")
        if target_prefix and not target.startswith(target_prefix):
            continue
        when = rule.get("when")
        if when and not _matches_when(when, payload):
            continue
        effect = rule.get("effect", "BLOCK")
        return {
            "decision": effect if effect != "ALLOW" else "ALLOW",
            "matched_rule_id": rule.get("id"),
            "risk_level": rule.get("risk_level", "HIGH"),
            "reason": rule.get("reason", "Rule matched"),
        }
    return {
        "decision": "BLOCK",
        "matched_rule_id": "rule-default-deny",
        "risk_level": "HIGH",
        "reason": "No matching rule — default deny",
    }
