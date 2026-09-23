"""Evaluation lab — run test cases against policy engine."""

import json
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

EVAL_DATASET_PATH = Path(__file__).resolve().parent.parent / "eval" / "cases.jsonl"


def load_eval_cases() -> list[dict[str, Any]]:
    if not EVAL_DATASET_PATH.exists():
        return []
    cases = []
    with open(EVAL_DATASET_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def run_evaluation(client: TestClient) -> dict[str, Any]:
    cases = load_eval_cases()
    results = []
    passed = 0

    for case in cases:
        case_id = case["case_id"]
        payload = {
            "agent_id": case.get("agent_id", "support-agent"),
            "action_type": case["tool_id"],
            "target": case.get("target", "order:2481"),
            "payload": case.get("arguments", {}),
            "idempotency_key": f"eval-{case_id}",
            "execution_id": case.get("execution_id"),
        }
        response = client.post("/api/v1/actions", json=payload)
        actual = response.json().get("status", "ERROR") if response.status_code == 200 else "ERROR"
        expected = case["expected_decision"]
        # Map internal status to decision
        decision_map = {
            "EXECUTED": "ALLOW",
            "REQUIRE_APPROVAL": "REQUIRE_APPROVAL",
            "BLOCKED": "BLOCK",
        }
        actual_decision = decision_map.get(actual, actual)
        match = actual_decision == expected
        if match:
            passed += 1
        results.append({
            "case_id": case_id,
            "category": case.get("category", "general"),
            "expected_decision": expected,
            "actual_decision": actual_decision,
            "policy_exact_match": match,
            "trace_complete": bool(response.json().get("id")) if response.status_code == 200 else False,
        })

    total = len(cases)
    return {
        "total_cases": total,
        "passed": passed,
        "failed": total - passed,
        "policy_exact_match_pct": round((passed / total) * 100, 1) if total else 0,
        "results": results,
    }
