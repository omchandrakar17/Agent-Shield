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

APP_ENV="${AGENTSHIELD_ENV:-production}"

if [ -n "$CLOUD_SQL_INSTANCE" ]; then
  echo "==> Running Alembic once (Cloud Run job agentshield-migrate)"
  gcloud run jobs deploy agentshield-migrate \
    --image="$IMAGE" \
    --region="$REGION" \
    --command=python \
    --args=-m,alembic,upgrade,head \
    --set-secrets=AGENTSHIELD_DATABASE_URL=agentshield-database-url:latest \
    --set-env-vars="AGENTSHIELD_ENV=${APP_ENV},AGENTSHIELD_RUN_MIGRATIONS=false" \
    --set-cloudsql-instances="$CLOUD_SQL_INSTANCE" \
    --max-retries=0 \
    --task-timeout=600 \
    --quiet
  gcloud run jobs execute agentshield-migrate --region="$REGION" --wait
else
  echo "Skipping Alembic: CLOUD_SQL_INSTANCE is empty."
fi

echo "==> Deploying to Cloud Run"
ENV_VARS="AGENTSHIELD_ENV=${APP_ENV},AGENTSHIELD_AUTH_MODE=local,AGENTSHIELD_SEED_USERS=false,AGENTSHIELD_USE_SECRET_MANAGER=true,AGENTSHIELD_USE_PUBSUB=true,AGENTSHIELD_USE_FIRESTORE=true,AGENTSHIELD_USE_BIGQUERY=true,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},AGENTSHIELD_RUN_MIGRATIONS=false,AGENTSHIELD_AGENT_PLANNER=vertex,VERTEX_GEMINI_MODEL=gemini-2.0-flash-001"
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
