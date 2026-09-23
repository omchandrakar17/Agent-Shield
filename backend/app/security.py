from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any

SENSITIVE_KEYS = {"password", "secret", "token", "key", "authorization", "api_key", "apikey", "access_token"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_payload(value: Any) -> Any:
    """Canonicalize nested structures: recursively sorts dicts, normalizes numbers and strings."""
    if isinstance(value, dict):
        normalized = {}
        for k in sorted(value.keys()):
            v = value[k]
            normalized[str(k)] = normalize_payload(v)
        return normalized
    elif isinstance(value, list):
        return [normalize_payload(item) for item in value]
    elif isinstance(value, float):
        # Round floats to 6 decimal places to prevent float representation divergence
        return round(value, 6)
    elif isinstance(value, str):
        return value.strip()
    return value


def canonical_hash(value: Any) -> str:
    normalized = normalize_payload(value)
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + sha256(encoded).hexdigest()


def generate_approval_fingerprint(
    action_id: str,
    agent_id: str,
    action_type: str,
    target: str,
    payload_hash: str,
    policy_version: int,
) -> str:
    envelope = {
        "action_id": action_id,
        "agent_id": agent_id,
        "action_type": action_type,
        "target": target,
        "payload_hash": payload_hash,
        "policy_version": policy_version,
    }
    return canonical_hash(envelope)


def redact_data(data: Any) -> Any:
    if isinstance(data, dict):
        redacted = {}
        for k, v in data.items():
            if any(s in str(k).lower() for s in SENSITIVE_KEYS):
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = redact_data(v)
        return redacted
    elif isinstance(data, list):
        return [redact_data(item) for item in data]
    elif isinstance(data, str):
        # Credit card masking pattern
        if re.search(r"\b(?:\d{4}[ -]?){3}\d{4}\b", data):
            return re.sub(r"\b(?:\d{4}[ -]?){3}\d{4}\b", "[REDACTED_CC]", data)
        return data
    return data
