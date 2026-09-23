"""Authentication API — registration, login, password reset."""

import secrets
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import OperatorDep
from app.auth import OperatorContext, create_access_token, get_auth_mode, verify_firebase_token
from app.core.config import get_settings
from app.database import get_db
from app.models import InvitationModel, UserModel
from app.security import now
from app.services.auth_service import (
    accept_invitation,
    authenticate_user,
    confirm_password_reset,
    create_password_reset,
    register_organization,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=10)
    new_password: str = Field(min_length=8)


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="VIEWER")


class AcceptInviteRequest(BaseModel):
    token: str
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1)


class FirebaseLoginRequest(BaseModel):
    id_token: str = Field(min_length=10)


@router.get("/config")
def auth_config() -> dict:
    settings = get_settings()
    firebase_config = None
    if settings.auth_mode == "firebase":
        import os
        if os.getenv("VITE_FIREBASE_API_KEY"):
            firebase_config = {
                "apiKey": os.getenv("VITE_FIREBASE_API_KEY"),
                "authDomain": os.getenv("VITE_FIREBASE_AUTH_DOMAIN"),
                "projectId": os.getenv("VITE_FIREBASE_PROJECT_ID"),
            }
    return {
        "auth_mode": get_auth_mode(),
        "environment": settings.environment,
        "firebase": firebase_config,
    }


@router.post("/register")
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    try:
        user, org, membership = register_organization(
            db, body.organization_name, body.email, body.password, body.display_name
        )
    except ValueError as exc:
        if str(exc) == "EMAIL_EXISTS":
            raise HTTPException(status_code=409, detail={"code": "EMAIL_EXISTS", "message": "Email already registered"})
        raise
    token = create_access_token(user.id, user.email, membership.role, user.display_name, org.id, "local")
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": membership.role,
            "organization_id": org.id,
            "organization_name": org.name,
        },
    }


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)) -> dict:
    if get_auth_mode() == "disabled":
        token = create_access_token("anonymous", body.email, "ORG_OWNER", "Anonymous", "org-default", "disabled")
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {"email": body.email, "role": "ORG_OWNER", "organization_id": "org-default"},
        }

    try:
        user, membership = authenticate_user(db, body.email, body.password)
    except ValueError:
        raise HTTPException(status_code=401, detail={"code": "AUTH_INVALID", "message": "Invalid email or password"})

    from app.models import OrganizationModel
    org = db.query(OrganizationModel).filter(OrganizationModel.id == membership.organization_id).first()
    token = create_access_token(
        user.id, user.email, membership.role, user.display_name, membership.organization_id, "local"
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": membership.role,
            "organization_id": membership.organization_id,
            "organization_name": org.name if org else None,
        },
    }


@router.post("/password-reset/request")
def password_reset_request(body: PasswordResetRequest, db: Session = Depends(get_db)) -> dict:
    reset = create_password_reset(db, body.email)
    # In production: send email via SendGrid/SES. Token returned only in development.
    response: dict = {"message": "If the account exists, a reset link has been sent."}
    if get_settings().environment == "development" and reset:
        response["reset_token"] = reset.token
    return response


@router.post("/password-reset/confirm")
def password_reset_confirm(body: PasswordResetConfirm, db: Session = Depends(get_db)) -> dict:
    if not confirm_password_reset(db, body.token, body.new_password):
        raise HTTPException(status_code=400, detail={"code": "INVALID_TOKEN", "message": "Invalid or expired reset token"})
    return {"message": "Password updated successfully"}


@router.post("/invitations")
def create_invitation(
    body: InviteRequest,
    operator: OperatorContext = OperatorDep,
    db: Session = Depends(get_db),
) -> dict:
    from datetime import datetime, timedelta, timezone
    from app.core.rbac import Role, role_has_permission, Permission

    if not role_has_permission(operator.role, Permission.USER_MANAGE):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot invite users"})

    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    inv = InvitationModel(
        id=f"inv-{uuid4().hex[:10]}",
        organization_id=operator.organization_id,
        email=body.email.strip().lower(),
        role=body.role if body.role in {r.value for r in Role} else Role.VIEWER.value,
        token=token,
        invited_by=operator.user_id,
        expires_at=expires,
        created_at=now(),
    )
    db.add(inv)
    db.commit()
    result = {"id": inv.id, "email": inv.email, "role": inv.role, "expires_at": inv.expires_at}
    if get_settings().environment == "development":
        result["invitation_token"] = token
    return result


@router.post("/invitations/accept")
def accept_invite(body: AcceptInviteRequest, db: Session = Depends(get_db)) -> dict:
    try:
        user, membership = accept_invitation(db, body.token, body.password, body.display_name)
    except ValueError as exc:
        code = str(exc)
        raise HTTPException(status_code=400, detail={"code": code, "message": "Invitation invalid"})
    token = create_access_token(
        user.id, user.email, membership.role, user.display_name, membership.organization_id, "local"
    )
    return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "email": user.email, "role": membership.role}}


@router.post("/firebase")
def firebase_login(body: FirebaseLoginRequest) -> dict:
    operator = verify_firebase_token(body.id_token)
    token = create_access_token(
        operator.user_id,
        operator.email,
        operator.role,
        operator.display_name,
        operator.organization_id,
        "firebase",
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": operator.user_id,
            "email": operator.email,
            "role": operator.role,
            "display_name": operator.display_name,
            "organization_id": operator.organization_id,
        },
    }


@router.get("/me")
def auth_me(operator: OperatorContext = OperatorDep, db: Session = Depends(get_db)) -> dict:
    user = db.query(UserModel).filter(UserModel.id == operator.user_id).first()
    from app.models import OrganizationModel
    org = db.query(OrganizationModel).filter(OrganizationModel.id == operator.organization_id).first()
    return {
        "id": operator.user_id,
        "email": operator.email,
        "display_name": operator.display_name,
        "role": operator.role,
        "organization_id": operator.organization_id,
        "organization_name": org.name if org else None,
        "email_verified": user.email_verified if user else False,
        "auth_provider": operator.auth_provider,
    }
