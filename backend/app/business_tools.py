"""Sandbox business tool APIs — real state mutations for demo."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

# In-memory sandbox store (persisted across requests within process; orders also in DB when available)
SANDBOX_ORDERS: dict[str, dict] = {
    "2481": {
        "order_id": "2481",
        "customer_id": "cust_901",
        "status": "SHIPPED",
        "total_inr": 12500,
        "items": [{"sku": "WIDGET-A", "qty": 2}],
        "shipping_address": "42 Demo Street, Mumbai",
    },
    "2482": {
        "order_id": "2482",
        "customer_id": "cust_902",
        "status": "DELIVERED",
        "total_inr": 8900,
        "items": [{"sku": "GADGET-B", "qty": 1}],
        "shipping_address": "9 Test Lane, Bengaluru",
    },
}

SANDBOX_CUSTOMERS: dict[str, dict] = {
    "cust_901": {"customer_id": "cust_901", "name": "Demo Customer", "email": "demo@example.com", "status": "ACTIVE"},
    "cust_902": {"customer_id": "cust_902", "name": "Test User", "email": "test@example.com", "status": "ACTIVE"},
}

SANDBOX_REFUNDS: list[dict] = []

REFUND_POLICY = {
    "policy_version": "2026.09.1",
    "max_autonomous_refund_inr": 10000,
    "currency": "INR",
    "requires_approval_above": 10000,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def execute_business_tool(tool_id: str, target: str, payload: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Execute a registered business tool. dry_run=True reproduces decision without mutation."""
    request_id = f"req-{uuid4().hex[:10]}"
    executed_at = _now()

    if tool_id == "get_order":
        order_id = target.replace("order:", "") if target.startswith("order:") else target
        order = SANDBOX_ORDERS.get(order_id)
        if not order:
            return {
                "tool_id": tool_id,
                "request_id": request_id,
                "executed_at": executed_at,
                "schema_version": "1.0",
                "success": False,
                "error": f"Order {order_id} not found",
            }
        return {
            "tool_id": tool_id,
            "request_id": request_id,
            "executed_at": executed_at,
            "schema_version": "1.0",
            "success": True,
            "dry_run": dry_run,
            "payload": {**order, "include_shipping": payload.get("include_shipping", True)},
        }

    if tool_id == "get_customer":
        customer_id = payload.get("customer_id") or target.replace("customer:", "")
        customer = SANDBOX_CUSTOMERS.get(customer_id)
        if not customer:
            return {
                "tool_id": tool_id,
                "request_id": request_id,
                "executed_at": executed_at,
                "schema_version": "1.0",
                "success": False,
                "error": f"Customer {customer_id} not found",
            }
        return {
            "tool_id": tool_id,
            "request_id": request_id,
            "executed_at": executed_at,
            "schema_version": "1.0",
            "success": True,
            "dry_run": dry_run,
            "payload": customer,
        }

    if tool_id == "search_refund_policy":
        return {
            "tool_id": tool_id,
            "request_id": request_id,
            "executed_at": executed_at,
            "schema_version": "1.0",
            "success": True,
            "dry_run": dry_run,
            "payload": REFUND_POLICY,
        }

    if tool_id == "issue_refund":
        order_id = target.replace("order:", "") if target.startswith("order:") else payload.get("order_id", "2481")
        amount = float(payload.get("amount", 0))
        if dry_run:
            return {
                "tool_id": tool_id,
                "request_id": request_id,
                "executed_at": executed_at,
                "schema_version": "1.0",
                "success": True,
                "dry_run": True,
                "payload": {
                    "order_id": order_id,
                    "amount": amount,
                    "currency": payload.get("currency", "INR"),
                    "would_mutate": True,
                },
            }
        refund = {
            "refund_id": f"ref-{uuid4().hex[:8]}",
            "order_id": order_id,
            "amount": amount,
            "currency": payload.get("currency", "INR"),
            "recipient": payload.get("recipient", "cust_901"),
            "status": "COMPLETED",
            "processed_at": executed_at,
        }
        SANDBOX_REFUNDS.append(refund)
        if order_id in SANDBOX_ORDERS:
            SANDBOX_ORDERS[order_id]["status"] = "REFUNDED"
        return {
            "tool_id": tool_id,
            "request_id": request_id,
            "executed_at": executed_at,
            "schema_version": "1.0",
            "success": True,
            "dry_run": False,
            "payload": refund,
        }

    if tool_id == "update_shipping":
        order_id = target.replace("order:", "") if target.startswith("order:") else target
        if dry_run:
            return {
                "tool_id": tool_id,
                "request_id": request_id,
                "executed_at": executed_at,
                "schema_version": "1.0",
                "success": True,
                "dry_run": True,
                "payload": {"order_id": order_id, "address": payload.get("address")},
            }
        if order_id not in SANDBOX_ORDERS:
            return {
                "tool_id": tool_id,
                "request_id": request_id,
                "executed_at": executed_at,
                "schema_version": "1.0",
                "success": False,
                "error": f"Order {order_id} not found",
            }
        SANDBOX_ORDERS[order_id]["shipping_address"] = payload.get("address", "")
        return {
            "tool_id": tool_id,
            "request_id": request_id,
            "executed_at": executed_at,
            "schema_version": "1.0",
            "success": True,
            "dry_run": False,
            "payload": {"order_id": order_id, "shipping_address": SANDBOX_ORDERS[order_id]["shipping_address"]},
        }

    if tool_id == "delete_customer":
        return {
            "tool_id": tool_id,
            "request_id": request_id,
            "executed_at": executed_at,
            "schema_version": "1.0",
            "success": False,
            "error": "delete_customer is disabled in demo environment",
        }

    return {
        "tool_id": tool_id,
        "request_id": request_id,
        "executed_at": executed_at,
        "schema_version": "1.0",
        "success": False,
        "error": f"Unknown tool: {tool_id}",
    }
