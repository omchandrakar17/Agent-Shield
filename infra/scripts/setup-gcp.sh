#!/usr/bin/env bash
# AgentShield GCP infrastructure bootstrap
# Usage: PROJECT_ID=my-project REGION=us-central1 ./infra/scripts/setup-gcp.sh

set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-agentshield}"

echo "==> Configuring project $PROJECT_ID"
gcloud config set project "$PROJECT_ID"

echo "==> Enabling APIs"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  sqladmin.googleapis.com \
  pubsub.googleapis.com \
  firestore.googleapis.com \
  bigquery.googleapis.com \
  logging.googleapis.com \
  firebasehosting.googleapis.com

echo "==> Artifact Registry"
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --description="AgentShield images" \
  2>/dev/null || true

echo "==> Pub/Sub topics"
gcloud pubsub topics create agentshield-events 2>/dev/null || true
gcloud pubsub topics create agentshield-audit-events 2>/dev/null || true

echo "==> Firestore (native mode)"
gcloud firestore databases create --location="$REGION" 2>/dev/null || true

echo "==> BigQuery dataset"
bq mk --dataset --location=US "${PROJECT_ID}:agentshield" 2>/dev/null || true
bq query --use_legacy_sql=false < infra/bigquery/audit_events.sql || true

echo "==> Placeholder secrets (replace values in Secret Manager console)"
for secret in agentshield-jwt-secret agentshield-agent-api-key agentshield-internal-service-key agentshield-database-url agentshield-cors-origins agentshield-gemini-api-key; do
  gcloud secrets create "$secret" --replication-policy=automatic 2>/dev/null || true
done

echo "Done. Next: set secret values and run cloudbuild deploy."
