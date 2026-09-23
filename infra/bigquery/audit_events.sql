-- BigQuery schema for audit event analytics
-- Run: bq query --use_legacy_sql=false < infra/bigquery/audit_events.sql

CREATE SCHEMA IF NOT EXISTS `agentshield`
OPTIONS (location = "US");

CREATE TABLE IF NOT EXISTS `agentshield.audit_events` (
  id STRING NOT NULL,
  organization_id STRING,
  event_type STRING,
  action_id STRING,
  approval_id STRING,
  request_id STRING,
  actor STRING,
  created_at TIMESTAMP,
  payload_hash STRING,
  event_hash STRING,
  data_json STRING
)
PARTITION BY DATE(created_at)
CLUSTER BY organization_id, event_type;
