"""Authentication and user lifecycle — persistent identity."""

import re
import secrets
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.passwords import hash_password, verify_password
from app.core.rbac import Role
from app.models import (
    InvitationModel,
    OrganizationMemberModel,
    OrganizationModel,
    PasswordResetModel,
    UserModel,
)
from app.security import now


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or f"org-{uuid4().hex[:8]}"


def register_organization(
    db: Session,
    organization_name: str,
    email: str,
    password: str,
    display_name: str,
) -> tuple[UserModel, OrganizationModel, OrganizationMemberModel]:
    email_norm = email.strip().lower()
    if db.query(UserModel).filter(UserModel.email == email_norm).first():
        raise ValueError("EMAIL_EXISTS")

    org_id = f"org-{uuid4().hex[:10]}"
    slug_base = _slugify(organization_name)
    slug = slug_base
    counter = 1
    while db.query(OrganizationModel).filter(OrganizationModel.slug == slug).first():
        slug = f"{slug_base}-{counter}"
        counter += 1

    ts = now()
    org = OrganizationModel(
        id=org_id,
        name=organization_name.strip(),
        slug=slug,
        status="ACTIVE",
        plan="standard",
        created_at=ts,
        updated_at=ts,
    )
    user = UserModel(
        id=f"user-{uuid4().hex[:10]}",
        email=email_norm,
        password_hash=hash_password(password),
        display_name=display_name.strip(),
        status="ACTIVE",
        email_verified=False,
        auth_provider="local",
        created_at=ts,
        updated_at=ts,
    )
    membership = OrganizationMemberModel(
        id=f"mem-{uuid4().hex[:10]}",
        organization_id=org_id,
        user_id=user.id,
        role=Role.ORG_OWNER.value,
        status="ACTIVE",
        created_at=ts,
    )
    db.add(org)
    db.flush()
    db.add(user)
    db.flush()
    db.add(membership)
    db.commit()
    db.refresh(user)
    db.refresh(org)
    db.refresh(membership)
    return user, org, membership


def authenticate_user(db: Session, email: str, password: str) -> tuple[UserModel, OrganizationMemberModel]:
    email_norm = email.strip().lower()
    user = db.query(UserModel).filter(UserModel.email == email_norm).first()
    if not user or not user.password_hash or user.status != "ACTIVE":
        raise ValueError("INVALID_CREDENTIALS")
    if not verify_password(password, user.password_hash):
        raise ValueError("INVALID_CREDENTIALS")

    membership = (
        db.query(OrganizationMemberModel)
        .filter(
            OrganizationMemberModel.user_id == user.id,
            OrganizationMemberModel.status == "ACTIVE",
        )
        .first()
    )
    if not membership:
        raise ValueError("NO_ORGANIZATION")
    return user, membership


def create_password_reset(db: Session, email: str) -> PasswordResetModel | None:
    user = db.query(UserModel).filter(UserModel.email == email.strip().lower()).first()
    if not user:
        return None
    from datetime import datetime, timedelta, timezone

    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    reset = PasswordResetModel(
        id=f"rst-{uuid4().hex[:10]}",
        user_id=user.id,
        token=token,
        expires_at=expires,
        created_at=now(),
    )
    db.add(reset)
    db.commit()
    return reset


def confirm_password_reset(db: Session, token: str, new_password: str) -> bool:
    from datetime import datetime, timezone

    reset = db.query(PasswordResetModel).filter(PasswordResetModel.token == token).first()
    if not reset or reset.used_at:
        return False
    if datetime.now(timezone.utc) > datetime.fromisoformat(reset.expires_at.replace("Z", "+00:00")):
        return False
    user = db.query(UserModel).filter(UserModel.id == reset.user_id).first()
    if not user:
        return False
    user.password_hash = hash_password(new_password)
    user.updated_at = now()
    reset.used_at = now()
    db.commit()
    return True


def accept_invitation(
    db: Session,
    token: str,
    password: str,
    display_name: str,
) -> tuple[UserModel, OrganizationMemberModel]:
    from datetime import datetime, timezone

    inv = db.query(InvitationModel).filter(InvitationModel.token == token, InvitationModel.status == "PENDING").first()
    if not inv:
        raise ValueError("INVALID_INVITATION")
    if datetime.now(timezone.utc) > datetime.fromisoformat(inv.expires_at.replace("Z", "+00:00")):
        inv.status = "EXPIRED"
        db.commit()
        raise ValueError("INVITATION_EXPIRED")

    email = inv.email.strip().lower()
    existing = db.query(UserModel).filter(UserModel.email == email).first()
    ts = now()
    if existing:
        user = existing
        if password:
            user.password_hash = hash_password(password)
    else:
        user = UserModel(
            id=f"user-{uuid4().hex[:10]}",
            email=email,
            password_hash=hash_password(password),
            display_name=display_name.strip(),
            status="ACTIVE",
            email_verified=False,
            auth_provider="local",
            created_at=ts,
            updated_at=ts,
        )
        db.add(user)

    membership = OrganizationMemberModel(
        id=f"mem-{uuid4().hex[:10]}",
        organization_id=inv.organization_id,
        user_id=user.id,
        role=inv.role,
        status="ACTIVE",
        created_at=ts,
    )
    inv.status = "ACCEPTED"
    db.add(membership)
    db.commit()
    db.refresh(user)
    db.refresh(membership)
    return user, membership
