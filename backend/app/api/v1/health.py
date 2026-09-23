"""Health check."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_auth_mode
from app.core.config import get_settings
from app.database import get_db
from app.policy_engine import ensure_default_policy
from app.registry import ensure_registry

router = APIRouter(tags=["health"])


@router.get("/health")
@router.get("/healthz")
def health(db: Session = Depends(get_db)) -> dict:
    ensure_default_policy(db)
    ensure_registry(db)
    settings = get_settings()
    return {
        "status": "ok",
        "service": "agentshield",
        "version": "1.0.0",
        "environment": settings.environment,
        "auth_mode": get_auth_mode(),
        "cloud": {
            "project_id": settings.gcp_project_id,
            "firestore": settings.use_firestore,
            "pubsub": settings.use_pubsub,
            "bigquery": settings.use_bigquery,
            "secret_manager": settings.use_secret_manager,
        },
    }
