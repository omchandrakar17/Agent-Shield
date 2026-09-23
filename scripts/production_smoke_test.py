#!/usr/bin/env python3
"""Post-deploy smoke test for AgentShield production/staging APIs."""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def request_json(
    method: str,
    url: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return exc.code, parsed


def login(base: str, email: str, password: str) -> str:
    status, body = request_json(
        "POST",
        f"{base}/api/v1/auth/login",
        {"email": email, "password": password},
    )
    if status != 200 or "access_token" not in body:
        raise RuntimeError(f"Login failed: HTTP {status} {body}")
    return body["access_token"]


def main() -> int:
    parser = argparse.ArgumentParser(description="AgentShield production smoke test")
    parser.add_argument("--base-url", required=True, help="Cloud Run or local API base URL")
    parser.add_argument("--runtime-api-key", default=None, help="X-Agent-Api-Key for runtime routes")
    parser.add_argument("--operator-email", default=None, help="Optional operator login for approval flow")
    parser.add_argument("--operator-password", default=None, help="Operator password")
    parser.add_argument("--with-approval", action="store_true", help="Also validate approval workflow")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    runtime_headers: dict[str, str] = {}
    if args.runtime_api_key:
        runtime_headers["X-Agent-Api-Key"] = args.runtime_api_key

    for path in ("/health", "/healthz"):
        status, health = request_json("GET", f"{base}{path}")
        if status == 200 and health.get("status") == "ok":
            print(f"Health check passed ({path})")
            break
    else:
        print(f"Health check failed: {health}")
        return 1

    read_action = {
        "agent_id": "support-agent",
        "action_type": "get_order",
        "target": "order:2481",
        "payload": {"include_shipping": True},
        "idempotency_key": f"smoke-read-{time.time_ns()}",
    }
    status, action = request_json("POST", f"{base}/api/v1/actions", read_action, runtime_headers)
    if status != 200:
        print(f"Read action failed: HTTP {status} {action}")
        return 1
    if action.get("status") not in {"EXECUTED", "ALLOWED"}:
        print(f"Unexpected read action status: {action}")
        return 1
    print(f"Runtime gateway read action OK (status={action.get('status')})")

    if args.with_approval:
        if not args.operator_email or not args.operator_password:
            print("--with-approval requires --operator-email and --operator-password")
            return 1

        token = login(base, args.operator_email, args.operator_password)
        auth_headers = {**runtime_headers, "Authorization": f"Bearer {token}"}

        refund_action = {
            "agent_id": "support-agent",
            "action_type": "issue_refund",
            "target": "order:2481",
            "payload": {"amount": 25000, "currency": "INR", "order_id": "2481", "recipient": "cust_901"},
            "idempotency_key": f"smoke-refund-{time.time_ns()}",
        }
        status, pending = request_json("POST", f"{base}/api/v1/actions", refund_action, runtime_headers)
        if status != 200 or pending.get("status") != "REQUIRE_APPROVAL":
            print(f"Refund approval path failed: HTTP {status} {pending}")
            return 1

        approval_id = pending.get("approval_id")
        if not approval_id:
            print(f"Missing approval_id: {pending}")
            return 1

        status, decision = request_json(
            "POST",
            f"{base}/api/v1/approvals/{approval_id}/decision",
            {"decision": "approved", "reviewer": "smoke-test", "reason": "Production smoke validation"},
            auth_headers,
        )
        if status != 200:
            print(f"Approval decision failed: HTTP {status} {decision}")
            return 1

        final_status = (decision.get("action") or {}).get("status")
        if final_status not in {"EXECUTED", "APPROVED"}:
            print(f"Approval did not execute action: {decision}")
            return 1
        print(f"Approval workflow OK (final status={final_status})")

    print("Smoke validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
