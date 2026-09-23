#!/usr/bin/env bash
# Grant IAM roles required for AgentShield production deployment.
# Usage: PROJECT_ID=my-project ./infra/scripts/setup-iam.sh

set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

echo "==> Granting Cloud Run compute SA permissions ($COMPUTE_SA)"
for role in \
  roles/secretmanager.secretAccessor \
  roles/cloudsql.client \
  roles/pubsub.publisher \
  roles/datastore.user \
  roles/bigquery.dataEditor \
  roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="$role" \
    --quiet >/dev/null
done

echo "==> Granting Cloud Build SA permissions ($BUILD_SA)"
for role in \
  roles/run.admin \
  roles/iam.serviceAccountUser \
  roles/artifactregistry.writer \
  roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${BUILD_SA}" \
    --role="$role" \
    --quiet >/dev/null
done

echo "IAM setup complete."
