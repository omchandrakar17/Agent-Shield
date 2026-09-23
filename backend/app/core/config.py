"""Centralized application configuration — all secrets from environment."""

import os
from functools import lru_cache


class Settings:
    def __init__(self) -> None:
        self.app_name: str = "AgentShield"
        self.app_version: str = "1.0.0"
        self.environment: str = os.getenv("AGENTSHIELD_ENV", "development")

        self.gcp_project_id: str | None = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
        self.gcp_region: str = os.getenv("GOOGLE_CLOUD_REGION", "us-central1")

        self.database_url: str = os.getenv(
            "AGENTSHIELD_DATABASE_URL",
            "sqlite:///./agentshield.db",
        )
        self.firestore_project_id: str | None = os.getenv("FIRESTORE_PROJECT_ID") or self.gcp_project_id
        self.firestore_database_id: str = os.getenv("FIRESTORE_DATABASE_ID", "(default)")
        self.use_firestore: bool = os.getenv("AGENTSHIELD_USE_FIRESTORE", "false").lower() == "true"

        self.use_bigquery: bool = os.getenv("AGENTSHIELD_USE_BIGQUERY", "false").lower() == "true"
        self.bigquery_dataset: str = os.getenv("AGENTSHIELD_BIGQUERY_DATASET", "agentshield")
        self.bigquery_audit_table: str = os.getenv("AGENTSHIELD_BIGQUERY_AUDIT_TABLE", "audit_events")

        self.auth_mode: str = os.getenv("AGENTSHIELD_AUTH_MODE", "local")
        self.jwt_secret: str = os.getenv("AGENTSHIELD_JWT_SECRET", "change-me-in-production")
        self.jwt_ttl_hours: int = int(os.getenv("AGENTSHIELD_JWT_TTL_HOURS", "12"))
        self.password_reset_ttl_hours: int = int(os.getenv("AGENTSHIELD_PASSWORD_RESET_TTL_HOURS", "1"))

        self.cors_origins: list[str] = os.getenv(
            "AGENTSHIELD_CORS_ORIGINS",
            "http://localhost:5173,http://localhost:3000",
        ).split(",")

        self.agent_api_key: str | None = os.getenv("AGENTSHIELD_AGENT_API_KEY")
        self.internal_service_key: str | None = os.getenv("AGENTSHIELD_INTERNAL_SERVICE_KEY")

        self.pubsub_topic: str = os.getenv("AGENTSHIELD_PUBSUB_TOPIC", "agentshield-events")
        self.pubsub_audit_topic: str = os.getenv("AGENTSHIELD_PUBSUB_AUDIT_TOPIC", "agentshield-audit-events")
        self.use_pubsub: bool = os.getenv("AGENTSHIELD_USE_PUBSUB", "false").lower() == "true"

        self.use_secret_manager: bool = os.getenv("AGENTSHIELD_USE_SECRET_MANAGER", "false").lower() == "true"

        self.model_armor_enabled: bool = (
            os.getenv("AGENTSHIELD_MODEL_ARMOR_ENABLED", "false").lower() == "true"
        )

        self.cloud_sql_instance: str | None = os.getenv("CLOUD_SQL_CONNECTION_NAME")

        # Agent planner: keyword (default) | gemini (API key) | vertex (Vertex AI)
        self.agent_planner: str = os.getenv("AGENTSHIELD_AGENT_PLANNER", "keyword")
        self.gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.vertex_gemini_model: str = os.getenv("VERTEX_GEMINI_MODEL", "gemini-2.0-flash-001")


@lru_cache
def get_settings() -> Settings:
    return Settings()
