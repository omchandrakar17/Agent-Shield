"""Google BigQuery — analytics warehouse for audit and runtime metrics."""

import json
import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger("agentshield.cloud.bigquery")

_client: "BigQueryAnalytics | None" = None


class BigQueryAnalytics:
    """Streams audit rows into BigQuery for long-term analytics."""

    def __init__(self, project_id: str, dataset_id: str, audit_table: str = "audit_events") -> None:
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.audit_table = audit_table
        self._client = None
        self._table_ref = f"{project_id}.{dataset_id}.{audit_table}"
        try:
            from google.cloud import bigquery  # type: ignore

            self._client = bigquery.Client(project=project_id)
            logger.info("BigQuery client initialized — table %s", self._table_ref)
        except ImportError:
            logger.warning("google-cloud-bigquery not installed — BigQuery sink disabled")
        except Exception as exc:
            logger.warning("BigQuery client init failed: %s", exc)

    @property
    def available(self) -> bool:
        return self._client is not None

    def insert_audit_row(self, audit_event: dict[str, Any]) -> bool:
        if not self._client:
            logger.debug("[SIMULATED BIGQUERY] audit row %s", audit_event.get("id"))
            return False
        try:
            row = {
                "id": audit_event.get("id"),
                "organization_id": audit_event.get("organization_id"),
                "event_type": audit_event.get("event_type"),
                "action_id": audit_event.get("action_id"),
                "approval_id": audit_event.get("approval_id"),
                "request_id": audit_event.get("request_id"),
                "actor": audit_event.get("actor"),
                "created_at": audit_event.get("created_at"),
                "payload_hash": audit_event.get("payload_hash"),
                "event_hash": audit_event.get("event_hash"),
                "data_json": json.dumps(audit_event.get("data") or {}),
            }
            errors = self._client.insert_rows_json(self._table_ref, [row])
            if errors:
                logger.error("BigQuery insert errors: %s", errors)
                return False
            return True
        except Exception as exc:
            logger.error("BigQuery insert failed: %s", exc)
            return False

    def query_dashboard_counts(self, organization_id: str) -> dict[str, int] | None:
        if not self._client:
            return None
        try:
            sql = f"""
                SELECT
                  COUNTIF(event_type = 'ACTION_DECISION') AS protected_tool_calls,
                  COUNTIF(JSON_VALUE(data_json, '$.status') = 'BLOCKED') AS blocked_actions
                FROM `{self._table_ref}`
                WHERE organization_id = @org_id
                  AND created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
            """
            from google.cloud import bigquery  # type: ignore

            job_config = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("org_id", "STRING", organization_id)]
            )
            result = list(self._client.query(sql, job_config=job_config).result())
            if not result:
                return {"protected_tool_calls": 0, "blocked_actions": 0}
            row = result[0]
            return {
                "protected_tool_calls": int(row.protected_tool_calls or 0),
                "blocked_actions": int(row.blocked_actions or 0),
            }
        except Exception as exc:
            logger.warning("BigQuery dashboard query failed: %s", exc)
            return None


def get_bigquery_client() -> BigQueryAnalytics | None:
    global _client
    if _client is not None:
        return _client

    settings = get_settings()
    if not settings.use_bigquery or not settings.gcp_project_id:
        return None

    _client = BigQueryAnalytics(
        project_id=settings.gcp_project_id,
        dataset_id=settings.bigquery_dataset,
        audit_table=settings.bigquery_audit_table,
    )
    return _client
