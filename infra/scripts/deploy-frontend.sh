#!/usr/bin/env bash
# Build frontend and deploy to Firebase Hosting.
# Usage: PROJECT_ID=my-project ./infra/scripts/deploy-frontend.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"

echo "==> Building frontend (API proxied via Firebase rewrites)"
cd "$ROOT/frontend"
npm ci
VITE_API_URL=/api/v1 npm run build

echo "==> Deploying Firebase Hosting"
cd "$ROOT"
firebase deploy --only hosting --project "$PROJECT_ID"

echo "Frontend deployed. API /api/* routes to Cloud Run service agentshield-api."
