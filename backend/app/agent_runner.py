"""Support agent intent parser — maps user requests to tool calls (ADK/Gemini-compatible pattern)."""

import re
from typing import Any


INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"you\s+are\s+now\s+",
    r"delete\s+(all\s+)?customer",
    r"disable\s+account",
    r"override\s+(security|policy)",
    r"system\s+prompt",
]


def detect_prompt_injection(user_request: str) -> bool:
    lower = user_request.lower()
    return any(re.search(p, lower) for p in INJECTION_PATTERNS)


def parse_user_intent(user_request: str) -> list[dict[str, Any]]:
    """
    Deterministic intent → tool call planner.
    Returns list of planned tool calls: [{tool_id, target, payload}, ...]
    """
    text = user_request.strip()
    lower = text.lower()
    planned: list[dict[str, Any]] = []

    # Attack path: prompt injection attempting unauthorized tool
    if detect_prompt_injection(text) or "delete_customer" in lower or "delete customer" in lower:
        customer_id = "cust_901"
        match = re.search(r"cust[_-]?\d+", lower)
        if match:
            customer_id = match.group(0).replace("-", "_")
        planned.append({
            "tool_id": "delete_customer",
            "target": f"customer:{customer_id}",
            "payload": {"customer_id": customer_id, "purge_pii": True},
            "reason": "Agent attempted critical destructive action",
        })
        return planned

    # Order lookup
    order_match = re.search(r"#?(\d{4})", text) or re.search(r"order\s+(\d+)", lower)
    order_id = order_match.group(1) if order_match else "2481"

    if any(kw in lower for kw in ["where is", "track", "status of", "get order", "order"]):
        if "refund" not in lower and "cancel" not in lower:
            planned.append({
                "tool_id": "get_order",
                "target": f"order:{order_id}",
                "payload": {"include_shipping": True},
                "reason": "User requested order status",
            })
            return planned

    # Refund path
    amount_match = re.search(r"(\d{1,3}(?:,\d{3})*|\d+)\s*(?:inr|₹|rs)?", lower)
    amount = 25000
    if amount_match:
        amount = int(amount_match.group(1).replace(",", ""))

    if any(kw in lower for kw in ["refund", "cancel", "return money"]):
        planned.append({
            "tool_id": "search_refund_policy",
            "target": "policy:refunds",
            "payload": {"policy_version": "2026.09.1"},
            "reason": "Check refund policy before financial action",
        })
        planned.append({
            "tool_id": "issue_refund",
            "target": f"order:{order_id}",
            "payload": {"amount": amount, "currency": "INR", "recipient": "cust_901", "order_id": order_id},
            "reason": f"User requested refund of {amount} INR",
        })
        return planned

    # Customer lookup
    if "customer" in lower:
        cust_match = re.search(r"cust[_-]?\d+", lower)
        customer_id = cust_match.group(0).replace("-", "_") if cust_match else "cust_901"
        planned.append({
            "tool_id": "get_customer",
            "target": f"customer:{customer_id}",
            "payload": {"customer_id": customer_id},
            "reason": "User requested customer information",
        })
        return planned

    # Default: safe read
    planned.append({
        "tool_id": "get_order",
        "target": f"order:{order_id}",
        "payload": {"include_shipping": True},
        "reason": "Default safe order lookup",
    })
    return planned
