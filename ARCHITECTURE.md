# AgentShield Architecture

AgentShield is a multi-tenant runtime authorization platform for AI agents. The AI model may recommend actions, but **server-side deterministic controls** make the final allow/block/approval decision.

## High-level flow

```
User → AI Agent → AgentShield Runtime Gateway → Identity + RBAC + Policy + Risk + Approval
  → ALLOW | BLOCK | REQUIRE_APPROVAL → Protected Tool/API → Audit + Trace
```

## Components

| Layer | Technology | Responsibility |
|-------|------------|----------------|
| Frontend | React + Vite | Landing, auth, operations console |
| API | FastAPI | Versioned REST (`/api/v1/*`) |
| Auth | Local JWT / Firebase | Registration, login, sessions |
| Data | SQLite (dev) / Firestore (prod target) | Tenant-scoped persistence |
| Policy engine | Python (deterministic) | Rule evaluation, no model authority |
| Runtime gateway | FastAPI middleware + services | Tool interception, schema validation |
| Business tools | Protected REST APIs | Reference customer-support tools |

## Multi-tenancy

Every operational entity carries `organization_id`. Queries are scoped server-side via `org_filter()` — never rely on frontend filtering alone.

### Roles (RBAC)

`PLATFORM_ADMIN`, `ORG_OWNER`, `SECURITY_ADMIN`, `AGENT_ADMIN`, `APPROVER`, `AUDITOR`, `VIEWER`

Permissions are enforced in API dependencies (`require_permission`).

## Code layout (Phase 3)

```
backend/app/
├── main.py                 # App factory + startup (~40 lines)
├── api/v1/
│   ├── router.py           # Aggregates all routers
│   ├── auth_routes.py      # /auth
│   ├── organizations.py    # /organizations
│   ├── agents.py           # /agents
│   ├── tools.py            # /tools
│   ├── policies.py         # /policies
│   ├── actions.py          # /actions (runtime gateway)
│   ├── executions.py       # /executions
│   ├── decisions.py        # /decisions/tool-call
│   ├── approvals.py        # /approvals
│   ├── audit.py            # /audit
│   ├── incidents.py        # /incidents
│   ├── kill_switches.py    # /kill-switches
│   ├── analytics.py        # /analytics
│   ├── business.py         # /business (internal only)
│   └── ...
├── services/
│   ├── action_service.py   # enforce_tool_call, serialize_action
│   ├── audit_service.py    # Tamper-evident audit log
│   ├── approval_service.py # Approval expiry
│   └── ...
├── runtime/                # Gateway hardening (Phase 2)
├── core/                   # HTTP errors, events, state machine
└── schemas/requests.py     # Pydantic request models
```

## API modules

- `/api/v1/auth` — register, login, password reset, invitations
- `/api/v1/organizations` — tenant settings, members
- `/api/v1/agents`, `/tools`, `/policies` — registry
- `/api/v1/actions`, `/executions`, `/approvals` — runtime
- `/api/v1/analytics` — dashboard metrics from real data
- `/api/v1/business/*` — protected reference APIs (internal key required)

## Runtime gateway (Phase 2)

All agent tool calls must pass through `/api/v1/actions`, `/api/v1/decisions/tool-call`, or `/api/v1/executions/{id}/run`.

| Control | Implementation |
|---------|----------------|
| Runtime auth | `X-Agent-Api-Key` header (`AGENTSHIELD_AGENT_API_KEY`) |
| Business API isolation | `X-Internal-Service-Key` on `/api/v1/business/*` |
| Kill switches | Global (`ControlModel`) + scoped (`KillSwitchModel`: ORG/AGENT/TOOL) |
| Tenant propagation | `organization_id` from agent record on actions/executions |
| Rate limits | Per org+agent+tool using `ToolModel.rate_limit_per_minute` |
| Agent lifecycle | `DRAFT`, `PAUSED`, `DISABLED`, `ARCHIVED` cannot execute |

## Security invariants

1. Unknown tools are denied by default
2. Disabled agents cannot execute protected actions
3. Approvals bind to exact argument hashes
4. Kill switches block execution at configured scope
5. Secrets never ship in frontend code
6. Dashboard numbers come from database queries only

## Cloud infrastructure (Phase 4)

```
                    ┌─────────────────┐
  Cloud Run API ───►│ SQL (primary)   │◄── Cloud SQL Postgres (prod)
                    └────────┬────────┘
                             │ audit_service.record_audit()
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        Pub/Sub topics   Firestore      BigQuery
        (events/audit)   (mirror)    (audit_events)
```

| Component | Module | Enable flag |
|-----------|--------|-------------|
| Secret Manager | `cloud/bootstrap.py` | `AGENTSHIELD_USE_SECRET_MANAGER` |
| Firestore mirror | `cloud/firestore_store.py` | `AGENTSHIELD_USE_FIRESTORE` |
| Pub/Sub | `cloud/adapters.py` | `AGENTSHIELD_USE_PUBSUB` |
| BigQuery | `cloud/bigquery_client.py` | `AGENTSHIELD_USE_BIGQUERY` |
| Cloud Logging | `cloud/logging_config.py` | auto in staging/production |

Deploy: `infra/cloudbuild.yaml` → Cloud Run. Bootstrap: `infra/scripts/setup-gcp.sh`.

See `DEPLOYMENT.md` for environment setup.

## Gemini / Vertex agent integration (Phase 5)

The support agent uses **function calling** to recommend tool invocations. Authorization always happens in `action_service.enforce_tool_call()` — Gemini never has final authority.

| Planner | Config | Use case |
|---------|--------|----------|
| `keyword` | `AGENTSHIELD_AGENT_PLANNER=keyword` | Local dev, tests (deterministic) |
| `gemini` | `AGENTSHIELD_AGENT_PLANNER=gemini` + `GEMINI_API_KEY` | Google AI Studio / API key |
| `vertex` | `AGENTSHIELD_AGENT_PLANNER=vertex` + `GOOGLE_CLOUD_PROJECT` | Production on GCP |

```
User request → plan_tool_calls() → Gemini recommends tools
              → enforce_tool_call() per tool → ALLOW / BLOCK / REQUIRE_APPROVAL
```

Modules: `app/agents/planner.py`, `app/agents/gemini_planner.py`, `app/agents/tool_declarations.py`.
