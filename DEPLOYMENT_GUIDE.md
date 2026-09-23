# AgentShield — GCP Deployment Guide

> Step-by-step instructions for deploying AgentShield to Google Cloud Platform using Cloud Run (backend) + Firebase Hosting (frontend).

---

## Prerequisites

### Tools required

| Tool | Version | Install |
|---|---|---|
| `gcloud` CLI | 460+ | https://cloud.google.com/sdk/docs/install |
| `firebase` CLI | 13+ | `npm install -g firebase-tools` |
| `docker` | 24+ | https://docs.docker.com/get-docker/ |
| `python` | 3.11+ | https://www.python.org/downloads/ |
| `node` | 20+ | https://nodejs.org/ |

### GCP project requirements

- A GCP project with billing enabled
- APIs enabled: Cloud Run, Cloud Build, Artifact Registry, Secret Manager, Cloud SQL Admin, Cloud Pub/Sub, Firebase

Enable all required APIs in one command:
```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  sqladmin.googleapis.com \
  pubsub.googleapis.com \
  firebase.googleapis.com \
  firebasehosting.googleapis.com
```

---

## Step 1 — GCP Project Setup

```bash
# Set your project ID
export PROJECT_ID=your-gcp-project-id
export REGION=us-central1
export REPO=agentshield

gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION
```

---

## Step 2 — Artifact Registry

```bash
# Create Docker repository
gcloud artifacts repositories create $REPO \
  --repository-format=docker \
  --location=$REGION \
  --description="AgentShield container images"

# Configure Docker auth
gcloud auth configure-docker $REGION-docker.pkg.dev
```

---

## Step 3 — Secret Manager Setup

Store secrets so they are never in environment variables or source control:

```bash
# Database connection string (Cloud SQL PostgreSQL)
echo -n "postgresql+pg8000://agentshield:PASSWORD@/agentshield?unix_sock=/cloudsql/PROJECT:REGION:INSTANCE/.s.PGSQL.5432" \
  | gcloud secrets create agentshield-database-url --data-file=-

# CORS origins (your Firebase Hosting URL)
echo -n "https://your-project.web.app,https://your-project.firebaseapp.com" \
  | gcloud secrets create agentshield-cors-origins --data-file=-

# Grant Cloud Run service account access
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## Step 4 — Cloud SQL PostgreSQL (Persistent Database)

> [!NOTE]
> The local SQLite default automatically becomes PostgreSQL in production when `AGENTSHIELD_DATABASE_URL` points to a Cloud SQL instance. No code changes required — the SQLAlchemy abstraction handles it.

```bash
# Create Cloud SQL instance (PostgreSQL 15)
gcloud sql instances create agentshield-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=$REGION \
  --storage-type=SSD \
  --storage-size=10GB \
  --backup \
  --enable-point-in-time-recovery

# Create database and user
gcloud sql databases create agentshield --instance=agentshield-db
gcloud sql users create agentshield \
  --instance=agentshield-db \
  --password=STRONG_PASSWORD_HERE

# Get connection name (needed for Cloud Run)
gcloud sql instances describe agentshield-db --format="value(connectionName)"
# Output: PROJECT:REGION:agentshield-db
```

---

## Step 5 — Cloud Pub/Sub (Event Sink)

```bash
# Create topic for audit events
gcloud pubsub topics create agentshield-audit-events

# Create BigQuery subscription (optional analytics sink)
gcloud pubsub subscriptions create agentshield-bq-sink \
  --topic=agentshield-audit-events \
  --bigquery-table=$PROJECT_ID:agentshield_analytics.audit_events \
  --create-schema \
  --use-topic-schema \
  --drop-unknown-fields
```

---

## Step 6 — Build and Push Images

### Option A: Automated CI/CD (recommended)

```bash
# Trigger Cloud Build pipeline (cloudbuild.yaml)
gcloud builds submit --config=cloudbuild.yaml \
  --substitutions=_REGION=$REGION,_REPO=$REPO .
```

### Option B: Manual Docker build and push

```bash
# Build backend
docker build -t $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/backend:latest ./backend

# Build frontend
docker build -t $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/frontend:latest ./frontend

# Push both images
docker push $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/backend:latest
docker push $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/frontend:latest
```

---

## Step 7 — Deploy Backend to Cloud Run

```bash
# Get Cloud SQL connection name
CLOUD_SQL_CN=$(gcloud sql instances describe agentshield-db --format="value(connectionName)")

gcloud run deploy agentshield-backend \
  --image=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/backend:latest \
  --region=$REGION \
  --platform=managed \
  --port=8080 \
  --min-instances=1 \
  --max-instances=10 \
  --memory=512Mi \
  --cpu=1 \
  --add-cloudsql-instances=$CLOUD_SQL_CN \
  --set-env-vars="AGENTSHIELD_ENV=production" \
  --set-env-vars="AGENTSHIELD_USE_PUBSUB=true" \
  --set-env-vars="AGENTSHIELD_PUBSUB_TOPIC=agentshield-audit-events" \
  --set-env-vars="AGENTSHIELD_USE_SECRET_MANAGER=true" \
  --set-env-vars="CLOUD_SQL_CONNECTION_NAME=$CLOUD_SQL_CN" \
  --allow-unauthenticated

# Get the backend URL
BACKEND_URL=$(gcloud run services describe agentshield-backend \
  --region=$REGION --format="value(status.url)")
echo "Backend URL: $BACKEND_URL"
```

---

## Step 8 — Deploy Frontend to Firebase Hosting

```bash
# Initialize Firebase (first time only)
firebase login
firebase init hosting --project=$PROJECT_ID

# Build the frontend with backend URL
VITE_API_BASE_URL=$BACKEND_URL npm --prefix frontend run build

# Deploy to Firebase Hosting
firebase deploy --only hosting --project=$PROJECT_ID
```

### Update firebase.json for API rewrites

Ensure `firebase.json` rewrites point to your Cloud Run backend:

```json
{
  "hosting": {
    "public": "frontend/dist",
    "rewrites": [
      {
        "source": "/api/**",
        "run": {
          "serviceId": "agentshield-backend",
          "region": "us-central1"
        }
      },
      { "source": "**", "destination": "/index.html" }
    ]
  }
}
```

---

## Step 9 — Run Database Migrations

On first deployment, run Alembic migrations against Cloud SQL:

```bash
# Connect via Cloud SQL Auth Proxy (local machine)
cloud-sql-proxy $CLOUD_SQL_CN --port=5432 &

# Run migrations against Cloud SQL
AGENTSHIELD_DATABASE_URL="postgresql+pg8000://agentshield:PASSWORD@localhost:5432/agentshield" \
  python -m alembic -c backend/alembic.ini upgrade head
```

> [!IMPORTANT]
> The Cloud Run Dockerfile runs `alembic upgrade head` on container start. For production, disable this and run migrations as a separate Cloud Build step to avoid race conditions with multiple instances.

---

## Step 10 — IAM Roles Required

| Service Account | Role | Why |
|---|---|---|
| Cloud Run compute SA | `roles/secretmanager.secretAccessor` | Read secrets |
| Cloud Run compute SA | `roles/cloudsql.client` | Connect to Cloud SQL |
| Cloud Run compute SA | `roles/pubsub.publisher` | Publish audit events |
| Cloud Build SA | `roles/run.admin` | Deploy Cloud Run services |
| Cloud Build SA | `roles/iam.serviceAccountUser` | Act as compute SA |
| Cloud Build SA | `roles/artifactregistry.writer` | Push images |

```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
COMPUTE_SA="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"
BUILD_SA="$PROJECT_NUMBER@cloudbuild.gserviceaccount.com"

# Grant Cloud Run SA permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$COMPUTE_SA" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$COMPUTE_SA" \
  --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$COMPUTE_SA" \
  --role="roles/pubsub.publisher"

# Grant Cloud Build SA permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$BUILD_SA" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$BUILD_SA" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$BUILD_SA" \
  --role="roles/artifactregistry.writer"
```

---

## Step 11 — Smoke Test the Deployment

```bash
# Health check
curl $BACKEND_URL/healthz

# Submit a test action
curl -X POST $BACKEND_URL/api/v1/actions \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "support-agent-01",
    "action_type": "get_order",
    "target": "order-service",
    "payload": {"order_id": "ORD-001"},
    "idempotency_key": "smoke-test-001"
  }'

# Verify audit log
curl $BACKEND_URL/api/v1/audit
```

---

## Environment Variables Reference

All variables supported by the AgentShield backend:

| Variable | Default | Description |
|---|---|---|
| `AGENTSHIELD_ENV` | `development` | Runtime environment tag (`development`/`production`) |
| `AGENTSHIELD_DATABASE_URL` | SQLite absolute path | SQLAlchemy URL. Use `postgresql+pg8000://...` for Cloud SQL |
| `CLOUD_SQL_CONNECTION_NAME` | — | Cloud SQL instance name (`PROJECT:REGION:INSTANCE`) |
| `AGENTSHIELD_CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed CORS origins |
| `AGENTSHIELD_USE_PUBSUB` | `false` | Enable Google Cloud Pub/Sub event publishing |
| `AGENTSHIELD_PUBSUB_TOPIC` | `agentshield-audit-events` | Pub/Sub topic name for audit events |
| `AGENTSHIELD_USE_SECRET_MANAGER` | `false` | Resolve secrets from Google Cloud Secret Manager |
| `AGENTSHIELD_MODEL_ARMOR_ENABLED` | `false` | Enable Model Armor prompt injection pre-flight |
| `APPROVAL_TTL_SECONDS` | `300` | Approval expiry window in seconds (default: 5 minutes) |

---

## Troubleshooting

### Cloud Run can't connect to Cloud SQL
- Ensure `--add-cloudsql-instances` flag is set on Cloud Run
- Verify the compute SA has `roles/cloudsql.client`
- Check the connection name format: `PROJECT:REGION:INSTANCE`

### Alembic migration fails on startup
- Check `AGENTSHIELD_DATABASE_URL` is set correctly
- For PostgreSQL, ensure `pg8000` driver is installed (included in `backend/pyproject.toml`)
- Verify database user has `CREATE TABLE` permissions

### Frontend shows CORS errors
- Update `AGENTSHIELD_CORS_ORIGINS` to include your Firebase Hosting URL
- Firebase rewrites in `firebase.json` should forward `/api/**` to Cloud Run

### Approval fingerprint mismatch (ARGUMENT_MISMATCH)
- This is correct security behavior — it means the approval payload was tampered
- Create a fresh action and approval; do not modify payload between submission and decision

---

## Local vs Cloud Parity

| Behavior | Local (SQLite) | Cloud (PostgreSQL + Cloud SQL) |
|---|---|---|
| Database | SQLite WAL file | PostgreSQL 15 on Cloud SQL |
| Event sink | In-memory ring buffer | Google Cloud Pub/Sub → BigQuery |
| Secrets | `.env` file | Google Cloud Secret Manager |
| Hosting | `uvicorn --reload` | Cloud Run (auto-scaling) |
| Frontend | Vite dev server | Firebase Hosting + CDN |
| Auth | None (dev) | Firebase Authentication (add for production) |

> [!NOTE]
> The local demo and cloud deployment use the **same codebase and same API contracts**. The pluggable adapter layer (`backend/app/cloud/adapters.py`) handles the switching transparently via environment variables.

