from abc import ABC, abstractmethod
import json
import logging
import os
from typing import Any

logger = logging.getLogger("agentshield.cloud")


# =====================================================================
# 1. Database Adapter Layer
# =====================================================================

class DatabaseAdapter(ABC):
    @abstractmethod
    def get_connection_url(self) -> str:
        """Returns the SQLAlchemy engine connection URL."""
        pass

    @abstractmethod
    def is_sqlite(self) -> bool:
        """Returns True if the engine is local SQLite."""
        pass


class SqliteAdapter(DatabaseAdapter):
    def __init__(self, db_path: str | None = None) -> None:
        if not db_path:
            backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            self.db_path = os.path.join(backend_dir, "agentshield.db").replace("\\", "/")
        else:
            self.db_path = db_path

    def get_connection_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    def is_sqlite(self) -> bool:
        return True


class PostgresCloudSqlAdapter(DatabaseAdapter):
    def __init__(
        self,
        db_user: str = "agentshield",
        db_pass: str = "password",
        db_name: str = "agentshield",
        instance_connection_name: str | None = None,
        db_host: str = "127.0.0.1",
        db_port: int = 5432,
    ) -> None:
        self.db_user = db_user
        self.db_pass = db_pass
        self.db_name = db_name
        self.instance_connection_name = instance_connection_name
        self.db_host = db_host
        self.db_port = db_port

    def get_connection_url(self) -> str:
        if self.instance_connection_name:
            # Cloud SQL socket / connector mode
            return f"postgresql+pg8000://{self.db_user}:{self.db_pass}@/{self.db_name}?unix_sock=/cloudsql/{self.instance_connection_name}/.s.PGSQL.5432"
        return f"postgresql://{self.db_user}:{self.db_pass}@{self.db_host}:{self.db_port}/{self.db_name}"

    def is_sqlite(self) -> bool:
        return False


class FirestoreAdapterInterface(ABC):
    """Abstract interface for future Google Cloud Firestore NoSQL storage."""

    @abstractmethod
    def get_collection(self, name: str) -> Any:
        pass


# =====================================================================
# 2. Telemetry & Event Sink Layer
# =====================================================================

class EventSink(ABC):
    @abstractmethod
    def publish_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Publishes real-time event for subscribers/SSE."""
        pass

    @abstractmethod
    def publish_audit(self, audit_event: dict[str, Any]) -> None:
        """Publishes append-only audit record to log sink or streaming analytics."""
        pass


class LocalEventSink(EventSink):
    def __init__(self, max_buffer: int = 500) -> None:
        self.events: list[dict[str, Any]] = []
        self.max_buffer = max_buffer

    def publish_event(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.append({"type": event_type, "data": data})
        if len(self.events) > self.max_buffer:
            del self.events[:100]

    def publish_audit(self, audit_event: dict[str, Any]) -> None:
        # In local mode, audit events are already committed to SQLite AuditEventModel
        pass


class GcpPubSubSink(EventSink):
    """Publishes events to Google Cloud Pub/Sub for BigQuery streaming ingestion."""

    def __init__(
        self,
        project_id: str,
        topic_id: str = "agentshield-audit-events",
        audit_topic_id: str | None = None,
    ) -> None:
        self.project_id = project_id
        self.topic_id = topic_id
        self.audit_topic_id = audit_topic_id or topic_id
        self.publisher = None
        self.topic_path = None
        self.audit_topic_path = None
        try:
            from google.cloud import pubsub_v1  # type: ignore

            self.publisher = pubsub_v1.PublisherClient()
            self.topic_path = self.publisher.topic_path(project_id, topic_id)
            self.audit_topic_path = self.publisher.topic_path(project_id, self.audit_topic_id)
            logger.info("GCP Pub/Sub sink: events=%s audit=%s", self.topic_path, self.audit_topic_path)
        except ImportError:
            logger.warning("google-cloud-pubsub not installed — Pub/Sub sink in simulated mode")

    def _publish(self, topic_path: str | None, message: dict[str, Any]) -> None:
        if self.publisher and topic_path:
            payload = json.dumps(message, default=str).encode("utf-8")
            future = self.publisher.publish(topic_path, payload, source="agentshield")
            future.add_done_callback(
                lambda f: logger.error("Pub/Sub publish failed: %s", f.exception()) if f.exception() else None
            )
        else:
            logger.debug("[SIMULATED PUBSUB] %s", message.get("event_type") or message.get("type"))

    def publish_event(self, event_type: str, data: dict[str, Any]) -> None:
        self._publish(self.topic_path, {"type": event_type, "data": data})

    def publish_audit(self, audit_event: dict[str, Any]) -> None:
        self._publish(self.audit_topic_path, {"type": "audit.created", "data": audit_event})


class CompositeEventSink(EventSink):
    """Fan-out to multiple sinks (e.g. local buffer + Pub/Sub)."""

    def __init__(self, sinks: list[EventSink]) -> None:
        self.sinks = sinks

    def publish_event(self, event_type: str, data: dict[str, Any]) -> None:
        for sink in self.sinks:
            sink.publish_event(event_type, data)

    def publish_audit(self, audit_event: dict[str, Any]) -> None:
        for sink in self.sinks:
            sink.publish_audit(audit_event)


# =====================================================================
# 3. Secret Provider Layer
# =====================================================================

class SecretProvider(ABC):
    @abstractmethod
    def get_secret(self, secret_name: str, default: str | None = None) -> str | None:
        pass


class EnvSecretProvider(SecretProvider):
    def get_secret(self, secret_name: str, default: str | None = None) -> str | None:
        return os.getenv(secret_name, default)


class GcpSecretManagerProvider(SecretProvider):
    """Resolves runtime secrets from Google Cloud Secret Manager."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        self.client = None
        try:
            from google.cloud import secretmanager  # type: ignore
            self.client = secretmanager.SecretManagerServiceClient()
        except ImportError:
            logger.warning("google-cloud-secret-manager not installed. Falling back to environment variables.")

    def get_secret(self, secret_name: str, default: str | None = None) -> str | None:
        if not self.client:
            return os.getenv(secret_name, default)
        try:
            name = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
            response = self.client.access_secret_version(name=name)
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            logger.warning(f"Failed to fetch secret '{secret_name}' from GCP Secret Manager: {e}. Falling back to env.")
            return os.getenv(secret_name, default)


# =====================================================================
# Provider Factories
# =====================================================================

def get_database_adapter() -> DatabaseAdapter:
    custom_url = os.getenv("AGENTSHIELD_DATABASE_URL")
    if custom_url:
        if custom_url.startswith("postgres"):
            return PostgresCloudSqlAdapter()
        return SqliteAdapter(custom_url.replace("sqlite:///", ""))

    cloud_sql_instance = os.getenv("CLOUD_SQL_CONNECTION_NAME")
    if cloud_sql_instance:
        return PostgresCloudSqlAdapter(
            db_user=os.getenv("DB_USER", "agentshield"),
            db_pass=os.getenv("DB_PASS", "agentshield"),
            db_name=os.getenv("DB_NAME", "agentshield"),
            instance_connection_name=cloud_sql_instance,
        )
    return SqliteAdapter()


def get_secret_provider() -> SecretProvider:
    gcp_project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    use_gsm = os.getenv("AGENTSHIELD_USE_SECRET_MANAGER", "false").lower() == "true"
    if gcp_project and use_gsm:
        return GcpSecretManagerProvider(gcp_project)
    return EnvSecretProvider()


def get_event_sink() -> EventSink:
    gcp_project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    use_pubsub = os.getenv("AGENTSHIELD_USE_PUBSUB", "false").lower() == "true"
    local = LocalEventSink()
    if gcp_project and use_pubsub:
        topic = os.getenv("AGENTSHIELD_PUBSUB_TOPIC", "agentshield-events")
        audit_topic = os.getenv("AGENTSHIELD_PUBSUB_AUDIT_TOPIC", "agentshield-audit-events")
        return CompositeEventSink([local, GcpPubSubSink(gcp_project, topic, audit_topic)])
    return local

