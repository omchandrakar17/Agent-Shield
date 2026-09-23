"""HTTP helpers — request IDs and structured errors."""

from uuid import uuid4

from fastapi import HTTPException, Request


def get_request_id(request: Request) -> str:
    return request.headers.get("x-request-id") or str(uuid4())


def api_error(
    code: str,
    message: str,
    request_id: str,
    status: int = 400,
    details: dict | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={
            "code": code,
            "message": message,
            "request_id": request_id,
            "details": details or {},
        },
    )
