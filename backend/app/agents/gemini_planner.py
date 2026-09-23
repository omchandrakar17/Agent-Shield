"""Vertex AI / Gemini tool-call planner — recommends actions, does not authorize them."""

import json
import logging
import re
from typing import Any

from app.agents.prompts import SUPPORT_AGENT_SYSTEM_PROMPT
from app.agents.tool_declarations import build_function_declarations
from app.core.config import get_settings

logger = logging.getLogger("agentshield.agents.gemini")


def _default_target(tool_id: str, args: dict[str, Any]) -> str:
    if tool_id == "get_order":
        return f"order:{args.get('order_id', '2481')}"
    if tool_id == "get_customer":
        return f"customer:{args.get('customer_id', 'cust_901')}"
    if tool_id == "issue_refund":
        return f"order:{args.get('order_id', '2481')}"
    if tool_id == "update_shipping":
        return f"order:{args.get('order_id', '2481')}"
    if tool_id == "delete_customer":
        return f"customer:{args.get('customer_id', 'cust_901')}"
    if tool_id == "search_refund_policy":
        return "policy:refunds"
    return f"resource:{tool_id}"


def _normalize_planned_call(tool_id: str, args: dict[str, Any], reason: str = "") -> dict[str, Any]:
    payload = dict(args or {})
    if tool_id == "get_order":
        if "order_id" in payload:
            order_id = str(payload.pop("order_id"))
            target = f"order:{order_id}"
        else:
            target = _default_target(tool_id, payload)
        payload.setdefault("include_shipping", True)
    elif tool_id == "issue_refund" and "order_id" not in payload:
        order_match = re.search(r"(\d{4})", reason)
        if order_match:
            payload.setdefault("order_id", order_match.group(1))
        payload.setdefault("currency", "INR")
        payload.setdefault("recipient", "cust_901")
        target = _default_target(tool_id, payload)
    else:
        target = _default_target(tool_id, payload)

    return {
        "tool_id": tool_id,
        "target": target,
        "payload": payload,
        "reason": reason or f"Gemini recommended {tool_id}",
    }


def parse_function_calls_from_response(response: Any, allowed_tools: set[str]) -> list[dict[str, Any]]:
    """Parse Gemini generate_content response into planned tool calls."""
    planned: list[dict[str, Any]] = []

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        parts = getattr(content, "parts", None) or []
        for part in parts:
            fc = getattr(part, "function_call", None)
            if fc is None and isinstance(part, dict):
                fc = part.get("function_call")
            if not fc:
                continue
            name = getattr(fc, "name", None) or (fc.get("name") if isinstance(fc, dict) else None)
            args = getattr(fc, "args", None) or (fc.get("args") if isinstance(fc, dict) else {}) or {}
            if isinstance(args, str):
                args = json.loads(args)
            if name and name in allowed_tools:
                planned.append(_normalize_planned_call(name, dict(args)))

    return planned


def _create_genai_client():
    settings = get_settings()
    try:
        from google import genai  # type: ignore
    except ImportError:
        logger.warning("google-genai not installed — pip install google-genai")
        return None, None

    if settings.agent_planner == "vertex" and settings.gcp_project_id:
        client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gcp_region,
        )
        model = settings.vertex_gemini_model
        return client, model

    if settings.gemini_api_key:
        client = genai.Client(api_key=settings.gemini_api_key)
        model = settings.gemini_model
        return client, model

    return None, None


def plan_with_gemini(user_request: str, allowed_tools: list[str] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Call Gemini with function calling to plan tool invocations.
    Returns (planned_calls, metadata). Falls back to empty list on failure.
    """
    settings = get_settings()
    allowed = set(allowed_tools or [])
    declarations = build_function_declarations(list(allowed) if allowed else None)
    if not declarations:
        return [], {"planner": "gemini", "error": "no_tools_available"}

    client, model = _create_genai_client()
    if not client or not model:
        return [], {"planner": "gemini", "error": "client_not_configured"}

    try:
        from google.genai import types  # type: ignore

        tools = [types.Tool(function_declarations=declarations)]
        config = types.GenerateContentConfig(
            tools=tools,
            system_instruction=SUPPORT_AGENT_SYSTEM_PROMPT,
            temperature=0.2,
            max_output_tokens=1024,
        )
        response = client.models.generate_content(
            model=model,
            contents=user_request,
            config=config,
        )
        planned = parse_function_calls_from_response(response, allowed if allowed else {d["name"] for d in declarations})
        if allowed:
            planned = [p for p in planned if p["tool_id"] in allowed]

        metadata = {
            "planner": "vertex" if settings.agent_planner == "vertex" else "gemini",
            "model": model,
            "tool_calls_recommended": len(planned),
        }
        return planned, metadata
    except Exception as exc:
        logger.exception("Gemini planning failed: %s", exc)
        return [], {"planner": "gemini", "error": str(exc)}
