"""Cloud platform bootstrap — secrets, logging, and service initialization."""

import logging
import os

from app.cloud.adapters import get_secret_provider
from app.core.config import get_settings

logger = logging.getLogger("agentshield.bootstrap")

# Env var -> Secret Manager secret id (without project prefix)
SECRET_BINDINGS: dict[str, str] = {
    "AGENTSHIELD_JWT_SECRET": "agentshield-jwt-secret",
    "AGENTSHIELD_AGENT_API_KEY": "agentshield-agent-api-key",
    "AGENTSHIELD_INTERNAL_SERVICE_KEY": "agentshield-internal-service-key",
    "AGENTSHIELD_DATABASE_URL": "agentshield-database-url",
    "AGENTSHIELD_CORS_ORIGINS": "agentshield-cors-origins",
    "GEMINI_API_KEY": "agentshield-gemini-api-key",
}


def load_secrets_from_manager() -> None:
    """Hydrate environment from Secret Manager when enabled (production)."""
    settings = get_settings()
    if not settings.use_secret_manager:
        return

    provider = get_secret_provider()
    loaded = 0
    for env_key, secret_id in SECRET_BINDINGS.items():
        if os.getenv(env_key):
            continue
        value = provider.get_secret(secret_id)
        if value:
            os.environ[env_key] = value
            loaded += 1
            logger.info("Loaded secret into %s from Secret Manager", env_key)

    if loaded:
        get_settings.cache_clear()
        logger.info("Secret Manager bootstrap complete (%d secrets loaded)", loaded)


def configure_cloud_logging() -> None:
    """Use Google Cloud Logging in production when available."""
    settings = get_settings()
    if settings.environment not in {"staging", "production"}:
        return
    try:
        import google.cloud.logging  # type: ignore

        client = google.cloud.logging.Client()
        client.setup_logging(log_level=logging.INFO)
        logger.info("Google Cloud Logging configured")
    except ImportError:
        logger.debug("google-cloud-logging not installed — using default logging")
    except Exception as exc:
        logger.warning("Cloud Logging setup failed: %s", exc)


def bootstrap_cloud_platform() -> None:
    """Run all cloud initialization steps at application startup."""
    load_secrets_from_manager()
    configure_cloud_logging()

    settings = get_settings()
    logger.info(
        "Cloud platform: env=%s firestore=%s pubsub=%s bigquery=%s secret_manager=%s",
        settings.environment,
        settings.use_firestore,
        settings.use_pubsub,
        settings.use_bigquery,
        settings.use_secret_manager,
    )
