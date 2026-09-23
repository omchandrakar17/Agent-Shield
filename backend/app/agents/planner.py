"""Unified agent planner — Gemini/Vertex when configured, keyword fallback otherwise."""

from typing import Any

from app.agent_runner import detect_prompt_injection, parse_user_intent
from app.agents.gemini_planner import plan_with_gemini
from app.core.config import get_settings


def resolve_planner_mode(agent_model_provider: str | None = None) -> str:
    """Returns: keyword | gemini | vertex"""
    settings = get_settings()
    if settings.agent_planner in {"keyword", "gemini", "vertex"}:
        return settings.agent_planner
    if agent_model_provider in {"gemini", "vertex", "vertex-ai"}:
        return "vertex" if agent_model_provider.startswith("vertex") else "gemini"
    return "keyword"


def plan_tool_calls(
    user_request: str,
    allowed_tools: list[str] | None = None,
    agent_model_provider: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Plan tool calls for an agent execution.
    The model recommends actions; AgentShield enforces authorization separately.

    Returns (planned_calls, metadata) where each call has tool_id, target, payload, reason.
    """
    mode = resolve_planner_mode(agent_model_provider)
    injection_detected = detect_prompt_injection(user_request)

    if mode in {"gemini", "vertex"}:
        planned, meta = plan_with_gemini(user_request, allowed_tools)
        meta["prompt_injection_detected"] = injection_detected
        if planned:
            meta["planner"] = mode
            return planned, meta
        # Fall through to keyword planner if Gemini unavailable or returned nothing

    # Keyword planner does not filter by allowlist — enforce_tool_call() blocks
    # unauthorized tools (needed for prompt-injection attack demos).
    planned = parse_user_intent(user_request)

    return planned, {
        "planner": "keyword",
        "model": None,
        "prompt_injection_detected": injection_detected,
        "tool_calls_recommended": len(planned),
        "fallback_from": mode if mode in {"gemini", "vertex"} else None,
    }
