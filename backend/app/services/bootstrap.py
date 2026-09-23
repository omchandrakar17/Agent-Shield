"""Bootstrap default organization and development seed data."""

import os
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.passwords import hash_password
from app.core.rbac import Role
from app.models import OrganizationMemberModel, OrganizationModel, UserModel
from app.security import now


DEFAULT_ORG_ID = "org-default"


def ensure_default_organization(db: Session) -> OrganizationModel:
    org = db.query(OrganizationModel).filter(OrganizationModel.id == DEFAULT_ORG_ID).first()
    ts = now()
    if not org:
        org = OrganizationModel(
            id=DEFAULT_ORG_ID,
            name="Default Organization",
            slug="default",
            status="ACTIVE",
            plan="standard",
            created_at=ts,
            updated_at=ts,
        )
        db.add(org)
        db.commit()
        db.refresh(org)
    return org


def should_seed_users() -> bool:
    """Seed dev users only in development unless explicitly overridden."""
    explicit = os.getenv("AGENTSHIELD_SEED_USERS")
    if explicit is not None:
        return explicit.lower() == "true"
    return os.getenv("AGENTSHIELD_ENV", "development") == "development"


def seed_development_users(db: Session) -> None:
    """Create persistent users for local development (not hardcoded auth bypass)."""
    if not should_seed_users():
        return

    ensure_default_organization(db)
    ts = now()

    legacy_emails = {
        "operator@agentshield.local": "operator@agentshield.example",
        "admin@agentshield.local": "admin@agentshield.example",
    }
    for old_email, new_email in legacy_emails.items():
        legacy_user = db.query(UserModel).filter(UserModel.email == old_email).first()
        if legacy_user:
            legacy_user.email = new_email
            legacy_user.updated_at = ts
    db.flush()

    seeds = [
        {
            "email": os.getenv("AGENTSHIELD_SEED_OPERATOR_EMAIL", "operator@agentshield.example"),
            "password": os.getenv("AGENTSHIELD_SEED_OPERATOR_PASSWORD", "agentshield2026"),
            "display_name": "Security Operator",
            "role": Role.SECURITY_ADMIN.value,
        },
        {
            "email": os.getenv("AGENTSHIELD_SEED_ADMIN_EMAIL", "admin@agentshield.example"),
            "password": os.getenv("AGENTSHIELD_SEED_ADMIN_PASSWORD", "admin2026"),
            "display_name": "Organization Owner",
            "role": Role.ORG_OWNER.value,
        },
    ]
    for seed in seeds:
        email = seed["email"].strip().lower()
        user = db.query(UserModel).filter(UserModel.email == email).first()
        if not user:
            user = UserModel(
                id=f"user-{uuid4().hex[:10]}",
                email=email,
                password_hash=hash_password(seed["password"]),
                display_name=seed["display_name"],
                status="ACTIVE",
                email_verified=True,
                auth_provider="local",
                created_at=ts,
                updated_at=ts,
            )
            db.add(user)
            db.flush()
            db.add(
                OrganizationMemberModel(
                    id=f"mem-{uuid4().hex[:10]}",
                    organization_id=DEFAULT_ORG_ID,
                    user_id=user.id,
                    role=seed["role"],
                    status="ACTIVE",
                    created_at=ts,
                )
            )
    db.commit()
