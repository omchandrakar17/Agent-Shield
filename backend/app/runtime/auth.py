"""Runtime gateway authentication — agent/service API key."""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request

from app.core.config import get_settings


@dataclass
class RuntimeContext:
    authenticated: bool
    auth_method: str  # api_key | dev_bypass


def verify_runtime_auth(request: Request) -> RuntimeContext:
    settings = get_settings()
    expected = settings.agent_api_key

    if not expected:
        if settings.environment == "production":
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "RUNTIME_AUTH_NOT_CONFIGURED",
                    "message": "AGENTSHIELD_AGENT_API_KEY must be set in production",
                },
            )
        return RuntimeContext(authenticated=False, auth_method="dev_bypass")

    provided = request.headers.get("x-agent-api-key") or request.headers.get("x-runtime-api-key")
    if not provided or provided != expected:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "RUNTIME_AUTH_INVALID",
                "message": "Valid X-Agent-Api-Key header required",
            },
        )
    return RuntimeContext(authenticated=True, auth_method="api_key")


def verify_internal_service(request: Request) -> None:
    """Protect direct business API access — tools must go through the gateway."""
    settings = get_settings()
    expected = settings.internal_service_key

    if not expected:
        if settings.environment == "production":
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "INTERNAL_AUTH_NOT_CONFIGURED",
                    "message": "AGENTSHIELD_INTERNAL_SERVICE_KEY must be set in production",
                },
            )
        return

    provided = request.headers.get("x-internal-service-key")
    if not provided or provided != expected:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "INTERNAL_AUTH_DENIED",
                "message": "Business APIs are internal-only. Route tool calls through AgentShield.",
            },
        )


RuntimeDep = Depends(verify_runtime_auth)
InternalServiceDep = Depends(verify_internal_service)
