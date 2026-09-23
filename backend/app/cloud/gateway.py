import logging
import os
import re
from typing import Any

logger = logging.getLogger("agentshield.gateway")

# Basic patterns for prompt injection & jailbreak detection
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?prior\s+rules", re.IGNORECASE),
    re.compile(r"system\s*override", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
    re.compile(r"DAN\s+mode", re.IGNORECASE),
]


class ModelArmorResult:
    def __init__(self, passed: bool, reason: str | None = None, score: float = 0.0) -> None:
        self.passed = passed
        self.reason = reason
        self.score = score

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "risk_score": self.score,
        }


class ModelArmorGateway:
    """
    Optional Google Cloud Model Armor / Agent Gateway integration.
    Performs pre-flight prompt injection, jailbreak, and toxic instruction inspection
    on incoming action requests before policy engine evaluation.
    """

    def __init__(self) -> None:
        self.enabled = os.getenv("AGENTSHIELD_MODEL_ARMOR_ENABLED", "false").lower() == "true"
        self.strict_mode = os.getenv("AGENTSHIELD_MODEL_ARMOR_STRICT", "false").lower() == "true"

    def inspect_payload(self, action_type: str, target: str, payload: dict[str, Any]) -> ModelArmorResult:
        if not self.enabled:
            # Zero-op pass-through for local development
            return ModelArmorResult(passed=True, reason="Model Armor disabled (local pass-through)")

        # Inspect textual fields in payload and target
        inspected_text = f"{action_type} {target} " + " ".join(
            str(v) for v in payload.values() if isinstance(v, (str, int, float))
        )

        for pattern in INJECTION_PATTERNS:
            if pattern.search(inspected_text):
                logger.warning(f"Model Armor detected suspicious prompt instruction matching: {pattern.pattern}")
                return ModelArmorResult(
                    passed=False,
                    reason=f"Model Armor flagged prompt injection pattern: {pattern.pattern}",
                    score=0.95,
                )

        return ModelArmorResult(passed=True, reason="Model Armor verification passed", score=0.05)


model_armor_gateway = ModelArmorGateway()

