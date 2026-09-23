#!/usr/bin/env bash
# Build and deploy AgentShield API to Cloud Run.
# Usage:
#   PROJECT_ID=my-project REGION=us-central1 ./infra/scripts/deploy-backend.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-agentshield-api}"
REPO="${REPO:-agentshield}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/api:latest"
CLOUD_SQL_INSTANCE="${CLOUD_SQL_INSTANCE:-}"

echo "==> Building API image"
docker build -t "$IMAGE" -f "$ROOT/backend/Dockerfile" "$ROOT/backend"

echo "==> Pushing image"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
docker push "$IMAGE"

echo "==> Deploying to Cloud Run"
ENV_VARS="AGENTSHIELD_ENV=production,AGENTSHIELD_AUTH_MODE=local,AGENTSHIELD_SEED_USERS=false,AGENTSHIELD_USE_SECRET_MANAGER=true,AGENTSHIELD_USE_PUBSUB=true,AGENTSHIELD_USE_FIRESTORE=true,AGENTSHIELD_USE_BIGQUERY=true,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},AGENTSHIELD_RUN_MIGRATIONS=true"
if [ -n "$CLOUD_SQL_INSTANCE" ]; then
  ENV_VARS="${ENV_VARS},CLOUD_SQL_CONNECTION_NAME=${CLOUD_SQL_INSTANCE}"
fi

DEPLOY_ARGS=(
  run deploy "$SERVICE"
  --image="$IMAGE"
  --region="$REGION"
  --platform=managed
  --allow-unauthenticated
  --port=8080
  --memory=512Mi
  --cpu=1
  --min-instances=1
  --set-secrets=AGENTSHIELD_JWT_SECRET=agentshield-jwt-secret:latest,AGENTSHIELD_AGENT_API_KEY=agentshield-agent-api-key:latest,AGENTSHIELD_INTERNAL_SERVICE_KEY=agentshield-internal-service-key:latest,AGENTSHIELD_DATABASE_URL=agentshield-database-url:latest,AGENTSHIELD_CORS_ORIGINS=agentshield-cors-origins:latest
  --set-env-vars="$ENV_VARS"
)

if [ -n "$CLOUD_SQL_INSTANCE" ]; then
  DEPLOY_ARGS+=(--add-cloudsql-instances="$CLOUD_SQL_INSTANCE")
fi

gcloud "${DEPLOY_ARGS[@]}"

URL="$(gcloud run services describe "$SERVICE" --region="$REGION" --format='value(status.url)')"
echo "Backend deployed: $URL"
