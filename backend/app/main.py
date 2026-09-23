"""AgentShield API — application entrypoint."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.cloud.bootstrap import bootstrap_cloud_platform
from app.cloud.logging_config import setup_logging
from app.core.config import get_settings
from app.database import init_db
from app.policy_engine import ensure_default_policy
from app.registry import ensure_registry


def _seed_on_startup() -> None:
    from app.database import SessionLocal
    from app.services.bootstrap import ensure_default_organization, seed_development_users

    db = SessionLocal()
    try:
        ensure_default_organization(db)
        seed_development_users(db)
        ensure_default_policy(db)
        ensure_registry(db)
    finally:
        db.close()


settings = get_settings()
setup_logging(settings.environment)
bootstrap_cloud_platform()

init_db()
_seed_on_startup()

app = FastAPI(title="AgentShield API", version="1.0.0")

origins = os.getenv("AGENTSHIELD_CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
