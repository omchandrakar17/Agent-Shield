# AgentShield Deployment

Production deployment targets **Google Cloud Run** (API) + **Firebase Hosting** (console), with Cloud SQL, Secret Manager, Pub/Sub, Firestore, and BigQuery.

## Phase 7 checklist

| Step | Command / artifact |
|------|-------------------|
| 1. Bootstrap GCP | `./infra/scripts/setup-gcp.sh` |
| 2. IAM roles | `./infra/scripts/setup-iam.sh` |
| 3. Set secrets | Secret Manager console (see below) |
| 4. Deploy all | `./infra/scripts/deploy-production.sh` |
| 5. CI/CD deploy | `gcloud builds submit --config=infra/cloudbuild.yaml .` |
| 6. Smoke test | `python scripts/production_smoke_test.py --base-url $URL --runtime-api-key $KEY` |

## One-command production deploy

```bash
export PROJECT_ID=your-gcp-project
export REGION=us-central1
export CLOUD_SQL_INSTANCE=your-gcp-project:us-central1:agentshield-db  # optional

chmod +x infra/scripts/*.sh
./infra/scripts/deploy-production.sh
```

This runs GCP bootstrap, deploys the API to Cloud Run, publishes the console to Firebase Hosting, and runs the post-deploy smoke test.

## Environments

| Environment | `AGENTSHIELD_ENV` | Database | Cloud services |
|-------------|-------------------|----------|----------------|
| development | `development` | SQLite | Disabled (local) |
| staging | `staging` | Cloud SQL Postgres | Secret Manager, Pub/Sub, Firestore, BigQuery |
| production | `production` | Cloud SQL Postgres | Full stack + BigQuery |

See `.env.staging.example` and `.env.production.example`. Application containers set `AGENTSHIELD_RUN_MIGRATIONS=false`. Alembic runs once, before the Cloud Run revision, as Cloud Run job `agentshield-migrate`.

Staging deploy:

```bash
export PROJECT_ID=your-staging-project-id
export REGION=us-central1
export AGENTSHIELD_ENV=staging
export CLOUD_SQL_INSTANCE=your-staging-project-id:us-central1:agentshield-db
./infra/scripts/deploy-production.sh
```

Or Cloud Build:

```bash
gcloud builds submit --config=infra/cloudbuild.yaml . \
  --substitutions=_ENV=staging,_REGION=us-central1,_CLOUD_SQL_INSTANCE=PROJECT:us-central1:agentshield-db
```

## Secrets (Secret Manager)

| Secret ID | Env var |
|-----------|---------|
| `agentshield-jwt-secret` | `AGENTSHIELD_JWT_SECRET` |
| `agentshield-agent-api-key` | `AGENTSHIELD_AGENT_API_KEY` |
| `agentshield-internal-service-key` | `AGENTSHIELD_INTERNAL_SERVICE_KEY` |
| `agentshield-database-url` | `AGENTSHIELD_DATABASE_URL` |
| `agentshield-cors-origins` | `AGENTSHIELD_CORS_ORIGINS` |
| `agentshield-gemini-api-key` | `GEMINI_API_KEY` |

Set `AGENTSHIELD_USE_SECRET_MANAGER=true` on Cloud Run. Secrets load at startup via `app/cloud/bootstrap.py`.

## Cloud Build pipeline

`infra/cloudbuild.yaml` runs:

1. Backend pytest
2. Frontend test + build
3. Docker build (with `[gcp]` deps)
4. Push to Artifact Registry
5. Run Alembic once (`agentshield-migrate`) when `_CLOUD_SQL_INSTANCE` is set
6. Deploy Cloud Run `agentshield-api` in `us-central1` with `AGENTSHIELD_RUN_MIGRATIONS=false`
7. Post-deploy smoke test

```bash
gcloud builds submit --config=infra/cloudbuild.yaml . \
  --substitutions=_CLOUD_SQL_INSTANCE=PROJECT:REGION:INSTANCE
```

## Production hardening defaults

- `AGENTSHIELD_SEED_USERS=false` on Cloud Run (no dev accounts in production)
- `AGENTSHIELD_AGENT_API_KEY` required when `AGENTSHIELD_ENV=production`
- `/health` and `/healthz` for probes
- Firebase `/api/**` rewrites → Cloud Run `agentshield-api`
- Frontend built with `VITE_API_URL=/api/v1` (same-origin via Hosting)

## Smoke test

```bash
URL=$(gcloud run services describe agentshield-api --region=us-central1 --format='value(status.url)')
KEY=$(gcloud secrets versions access latest --secret=agentshield-agent-api-key)

python scripts/production_smoke_test.py --base-url "$URL" --runtime-api-key "$KEY"

# Optional approval workflow (requires seeded operator or registered user)
python scripts/production_smoke_test.py --base-url "$URL" --runtime-api-key "$KEY" \
  --with-approval --operator-email operator@example.com --operator-password '***'
```

## Local Docker

```bash
docker build -t agentshield-api -f backend/Dockerfile backend
docker run -p 8080:8080 \
  -e AGENTSHIELD_ENV=development \
  -e AGENTSHIELD_AUTH_MODE=disabled \
  agentshield-api
```

## GitHub Actions

- **CI** (every push): `.github/workflows/ci.yml`
- **Deploy** (manual): `.github/workflows/deploy.yml` — requires `GCP_SA_KEY` secret

## Data flow

```
Runtime action → SQL (primary) → audit_service
                    ↓
              Pub/Sub (audit-events topic)
                    ↓
              BigQuery (audit_events table)
                    ↓
              Firestore mirror (audit_events, security_events)
```

## Install GCP Python deps (local)

```bash
pip install -e "./backend[gcp]"
```
