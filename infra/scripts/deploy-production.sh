#!/usr/bin/env bash
# Full production deployment: GCP bootstrap (optional), backend, frontend, smoke test.
# Usage:
#   PROJECT_ID=my-project REGION=us-central1 ./infra/scripts/deploy-production.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-agentshield-api}"
SKIP_BOOTSTRAP="${SKIP_BOOTSTRAP:-false}"
WITH_APPROVAL_SMOKE="${WITH_APPROVAL_SMOKE:-false}"

if [ "$SKIP_BOOTSTRAP" != "true" ]; then
  echo "==> Bootstrapping GCP infrastructure"
  PROJECT_ID="$PROJECT_ID" REGION="$REGION" "$ROOT/infra/scripts/setup-gcp.sh"
  PROJECT_ID="$PROJECT_ID" "$ROOT/infra/scripts/setup-iam.sh"
fi

echo "==> Deploying backend"
PROJECT_ID="$PROJECT_ID" REGION="$REGION" SERVICE="$SERVICE" \
  AGENTSHIELD_ENV="${AGENTSHIELD_ENV:-production}" \
  CLOUD_SQL_INSTANCE="${CLOUD_SQL_INSTANCE:-}" \
  "$ROOT/infra/scripts/deploy-backend.sh"

echo "==> Deploying frontend"
PROJECT_ID="$PROJECT_ID" "$ROOT/infra/scripts/deploy-frontend.sh"

URL="$(gcloud run services describe "$SERVICE" --region="$REGION" --format='value(status.url)')"
API_KEY="$(gcloud secrets versions access latest --secret=agentshield-agent-api-key)"

SMOKE_ARGS=(--base-url "$URL" --runtime-api-key "$API_KEY")
if [ "$WITH_APPROVAL_SMOKE" = "true" ]; then
  SMOKE_ARGS+=(--with-approval --operator-email "${OPERATOR_EMAIL:-operator@agentshield.example}" --operator-password "${OPERATOR_PASSWORD:-agentshield2026}")
fi

echo "==> Running production smoke test"
python "$ROOT/scripts/production_smoke_test.py" "${SMOKE_ARGS[@]}"

echo "Production deployment complete."
echo "  API:      $URL"
echo "  Console:  https://${PROJECT_ID}.web.app/console"
