# AgentShield: Enterprise AI-Agent Runtime Control Plane

AgentShield is an auditor-ready runtime control plane for AI agents. It intercepts sensitive agent tool calls, enforces deterministic guardrails, binds human approvals to cryptographic SHA-256 payload fingerprints, persists tamper-evident audit and trace telemetry, and provides an external emergency kill switch.

> [!NOTE]
> **Project Scope & Architecture**:
> - **Local Development (Default)**: SQLite WAL, in-memory events, full runtime gateway and console.
> - **Production (Phase 7)**: Cloud Run + Firebase Hosting, Secret Manager, Cloud SQL, Pub/Sub, Firestore, BigQuery. See [DEPLOYMENT.md](DEPLOYMENT.md).
> - **Live GCP deploy** requires your own GCP project, billing, and credentials — run `./infra/scripts/deploy-production.sh` when ready.

---

## Architecture & Pluggable Cloud Layer

```
gfg/
├── backend/
│   ├── Dockerfile               # Multi-stage rootless container build
│   ├── alembic/                 # Database migrations (initial_schema, add_phase5_fields)
│   ├── app/
│   │   ├── cloud/
│   │   │   ├── adapters.py      # Pluggable Database, EventSink & SecretProvider
│   │   │   └── gateway.py       # Google Cloud Model Armor / Agent Gateway hooks
│   │   ├── database.py          # SQLite WAL connection & session factory
│   │   ├── models.py            # SQLAlchemy models (Action, Approval, Policy, Control, Audit, Trace)
│   │   ├── policy_engine.py     # Deterministic rule evaluator & active policy resolution
│   │   ├── security.py          # Normalization, canonical hashing, fingerprinting, redaction
│   │   └── main.py              # FastAPI endpoints, state transitions, SSE stream
│   └── tests/
│       ├── test_api.py           # Core smoke test suite
│       ├── test_cloud_adapters.py# Cloud adapters & Model Armor unit tests
│       ├── test_persistence.py   # Restart persistence & DB session verification
│       └── test_state_machine.py # State machine, tamper detection, and error code regression tests
├── frontend/
│   ├── Dockerfile               # Multi-stage build with Nginx static asset serving
│   ├── nginx.conf               # SPA routing, security headers & gzip compression
│   ├── src/
│   │   ├── App.tsx              # Enterprise console UI with tabs & evidence modals
│   │   ├── App.test.tsx         # Vitest component test suite
│   │   └── styles.css           # Modern console styling
│   └── package.json
├── docker-compose.yml           # Container orchestration with persistent volume
├── cloudrun-backend.yaml        # Google Cloud Run service specification
├── firebase.json                # Firebase Hosting configuration for frontend console
├── cloudbuild.yaml              # Google Cloud Build CI/CD deployment pipeline
├── implementation_plan.md       # Technical design specification
└── walkthrough.md               # Verification results & demo walkthrough
```

---

## Execution Modes

### 1. Local Development Mode (Default)

Requires Python 3.11+ and Node.js 20+.

#### Backend
```powershell
cd C:\Users\LENOVO\OneDrive\Desktop\gfg
.\.venv\Scripts\Activate.ps1
pip install -e backend

# Run database migrations
.\.venv\Scripts\python -m alembic -c backend/alembic.ini upgrade head

# Start API server
uvicorn app.main:app --app-dir backend --reload --port 8000
```
Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

#### Frontend Console
```powershell
cd C:\Users\LENOVO\OneDrive\Desktop\gfg\frontend
npm.cmd install
npm.cmd run dev
```
Console dashboard is accessible at `http://localhost:5173`.

---

### 2. Containerized Mode (Docker / Compose)

When Docker is installed on your host:

```powershell
cd C:\Users\LENOVO\OneDrive\Desktop\gfg

# Build and start services
docker compose up --build

# Stop services
docker compose down
```
- **Backend API**: `http://localhost:8000` (persists SQLite database to `agentshield-data` volume)
- **Frontend Console**: `http://localhost:5173` (served via production Nginx)

---

### 3. Google Cloud Platform (GCP) Deployment

AgentShield is ready for deployment on Google Cloud Platform:

#### Automated CI/CD (Cloud Build)
Submit build pipeline using `cloudbuild.yaml`:
```powershell
gcloud builds submit --config=cloudbuild.yaml .
```

#### Manual Cloud Run Deployment
```powershell
# 1. Deploy Backend to Cloud Run
gcloud run deploy agentshield-backend \
  --image=us-central1-docker.pkg.dev/$PROJECT_ID/agentshield/backend:latest \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated

# 2. Deploy Frontend to Firebase Hosting
npm --prefix frontend run build
firebase deploy --only hosting
```

---

## Environment Variables & Provider Configuration

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `AGENTSHIELD_ENV` | `development` | Runtime environment (`development` or `production`). |
| `AGENTSHIELD_DATABASE_URL` | `sqlite:///<dir>/agentshield.db` | SQLAlchemy connection string. Set to `postgresql://...` for Cloud SQL. |
| `CLOUD_SQL_CONNECTION_NAME` | None | Cloud SQL instance connection string (format: `PROJECT:REGION:INSTANCE`). |
| `AGENTSHIELD_CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins (comma-separated). |
| `AGENTSHIELD_USE_PUBSUB` | `false` | When `true`, publishes audit events to Google Cloud Pub/Sub for BigQuery ingestion. |
| `AGENTSHIELD_PUBSUB_TOPIC` | `agentshield-audit-events` | Target Pub/Sub topic. |
| `AGENTSHIELD_USE_SECRET_MANAGER` | `false` | When `true`, resolves secrets from Google Cloud Secret Manager. |
| `AGENTSHIELD_MODEL_ARMOR_ENABLED`| `false` | When `true`, intercepts prompt injection and jailbreak patterns before policy evaluation. |

---

## Automated Verification

### Backend Tests (25/25 Passing)
```powershell
.\.venv\Scripts\pytest backend/tests -v
```
Validates:
- Baseline execution, approval creation, and kill switch (`test_api.py`).
- SQLite restart persistence across separate DB engine sessions (`test_persistence.py`).
- State machine invariants, rejection immutability, argument mutation detection, and approval TTL expiration (`test_state_machine.py`).
- Pluggable cloud adapters, ring buffers, environment secret resolution, and Model Armor pre-flight detection (`test_cloud_adapters.py`).

### Frontend Tests & Build (4/4 Passing)
```powershell
cd frontend
npm.cmd run test
npm.cmd run build
```

### Runtime Smoke Validation (Production-like)
```powershell
# Start the API in a terminal
cd C:\Users\LENOVO\OneDrive\Desktop\gfg
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --app-dir backend --reload --port 8000

# In a second terminal
python production_smoke_test.py --base-url http://localhost:8000
```
This validates the live control-plane path end-to-end:
- `/health` returns `ok`
- a risky action is created and requires approval
- the approval decision executes the action successfully
- the API remains operational through the standard runtime path

---

## Production Completion Checklist

The project is complete for the local and containerized production path. The remaining work is external deployment execution, not new feature implementation.

- [x] Durable SQLite persistence with WAL and migration bootstrap
- [x] Strict approval binding and tamper detection
- [x] Full action lifecycle and kill-switch enforcement
- [x] Policy lifecycle management and evidence model
- [x] Audit log + trace export path
- [x] Frontend enterprise console and tabbed operations view
- [x] Docker Compose local production parity
- [x] Cloud-style adapters for database, secret, and event sinks
- [x] Cloud Run and Firebase deployment templates
- [ ] Real GCP deployment in a live project with billing and credentials
- [ ] Live secret and database wiring in a real GCP environment

---

## Demo Story & Evidence Flow

1. **Safe Read (`get_order`)**: Evaluates rule `rule-read-order` (`ALLOW`), attaches policy `v1`, transitions to `EXECUTED`.
2. **Risky Refund (`issue_refund`)**: Evaluates rule `rule-refund-approval` (`REQUIRE_APPROVAL`), generates SHA-256 fingerprint, creates approval request.
3. **Approval Station**: Navigate to **Approvals** tab, verify exact payload and expiration timer, enter reviewer note, and click **Approve Exact Action**.
4. **Tamper Detection**: Altering payload arguments prior to approval triggers `ARGUMENT_MISMATCH` (HTTP 409).
5. **Emergency Lockdown**: Toggle emergency kill switch. Inbound actions are rejected with `KILL_SWITCH_ACTIVE` (HTTP 423), and pending approvals are immediately blocked.
6. **Trace Waterfall**: Open **Audit & Traces** tab or click **Trace** on any row to view execution spans (`policy_evaluation`, `approval_gate`, `sandbox_execution`).
7. **Restart Persistence**: Kill and restart server; verify all ledger history, policies, and audit logs persist intact from database.
