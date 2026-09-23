"""Operator authentication — local JWT, Firebase, or disabled (tests)."""

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request

from app.core.config import get_settings


def get_auth_mode() -> str:
    return get_settings().auth_mode.lower()  # disabled | local | demo | firebase


@dataclass
class OperatorContext:
    user_id: str
    email: str
    role: str
    display_name: str
    organization_id: str
    auth_provider: str  # local | firebase | disabled


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    display_name: str,
    organization_id: str,
    provider: str = "local",
) -> str:
    import jwt

    settings = get_settings()
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "display_name": display_name,
        "organization_id": organization_id,
        "provider": provider,
        "exp": _utcnow() + timedelta(hours=settings.jwt_ttl_hours),
        "iat": _utcnow(),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_local_token(token: str) -> OperatorContext:
    import jwt

    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail={"code": "AUTH_INVALID", "message": str(exc)})

    return OperatorContext(
        user_id=str(payload["sub"]),
        email=str(payload["email"]),
        role=str(payload.get("role", "VIEWER")),
        display_name=str(payload.get("display_name", payload["email"])),
        organization_id=str(payload.get("organization_id", "org-default")),
        auth_provider=str(payload.get("provider", "local")),
    )


def verify_firebase_token(token: str) -> OperatorContext:
    try:
        import firebase_admin
        from firebase_admin import auth as firebase_auth, credentials
        from sqlalchemy.orm import Session

        from app.database import SessionLocal
        from app.models import OrganizationMemberModel, UserModel

        settings = get_settings()
        if not firebase_admin._apps:
            if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                firebase_admin.initialize_app(credentials.Certificate(os.environ["GOOGLE_APPLICATION_CREDENTIALS"]))
            elif settings.firestore_project_id:
                firebase_admin.initialize_app(options={"projectId": settings.firestore_project_id})
            else:
                raise HTTPException(
                    status_code=503,
                    detail={"code": "AUTH_CONFIG", "message": "Firebase not configured"},
                )

        decoded: dict[str, Any] = firebase_auth.verify_id_token(token)
        email = decoded.get("email", "unknown@firebase.local")
        uid = decoded.get("uid", "unknown")

        db: Session = SessionLocal()
        try:
            user = db.query(UserModel).filter(UserModel.firebase_uid == uid).first()
            if not user:
                user = db.query(UserModel).filter(UserModel.email == email.lower()).first()
            if user:
                membership = (
                    db.query(OrganizationMemberModel)
                    .filter(OrganizationMemberModel.user_id == user.id, OrganizationMemberModel.status == "ACTIVE")
                    .first()
                )
                if membership:
                    return OperatorContext(
                        user_id=user.id,
                        email=user.email,
                        role=membership.role,
                        display_name=user.display_name,
                        organization_id=membership.organization_id,
                        auth_provider="firebase",
                    )
        finally:
            db.close()

        return OperatorContext(
            user_id=uid,
            email=email,
            role="VIEWER",
            display_name=decoded.get("name") or email,
            organization_id="org-default",
            auth_provider="firebase",
        )
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail={"code": "AUTH_CONFIG", "message": "firebase-admin not installed"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail={"code": "AUTH_INVALID", "message": str(exc)})


def extract_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return None


def get_current_operator(request: Request) -> OperatorContext:
    if get_auth_mode() == "disabled":
        return OperatorContext(
            user_id="anonymous",
            email="anonymous@local",
            role="ORG_OWNER",
            display_name="Anonymous (auth disabled)",
            organization_id="org-default",
            auth_provider="disabled",
        )

    token = extract_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "Authorization Bearer token required"},
        )

    if get_auth_mode() == "firebase":
        return verify_firebase_token(token)
    return verify_local_token(token)


def require_operator(request: Request) -> OperatorContext:
    return get_current_operator(request)


OperatorDep = Depends(require_operator)
