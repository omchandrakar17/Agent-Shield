"""Registered tool JSON schemas for argument validation."""

TOOL_SCHEMAS: dict[str, dict] = {
    "get_order": {
        "type": "object",
        "properties": {
            "include_shipping": {"type": "boolean"},
        },
        "additionalProperties": True,
    },
    "get_customer": {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "minLength": 1},
        },
        "required": ["customer_id"],
        "additionalProperties": False,
    },
    "search_refund_policy": {
        "type": "object",
        "properties": {
            "policy_version": {"type": "string"},
        },
        "additionalProperties": False,
    },
    "issue_refund": {
        "type": "object",
        "properties": {
            "amount": {"type": "number", "exclusiveMinimum": 0},
            "currency": {"type": "string", "minLength": 3, "maxLength": 3},
            "recipient": {"type": "string"},
            "order_id": {"type": "string"},
        },
        "required": ["amount", "currency"],
        "additionalProperties": False,
    },
    "update_shipping": {
        "type": "object",
        "properties": {
            "address": {"type": "string", "minLength": 5},
            "city": {"type": "string"},
        },
        "required": ["address"],
        "additionalProperties": False,
    },
    "delete_customer": {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "minLength": 1},
            "purge_pii": {"type": "boolean"},
        },
        "required": ["customer_id"],
        "additionalProperties": False,
    },
}
