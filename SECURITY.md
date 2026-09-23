# AgentShield Security Model

## Authentication layers

| Layer | Header / mechanism | Purpose |
|-------|-------------------|---------|
| Operator console | `Authorization: Bearer <JWT>` | Human operators (local JWT or Firebase) |
| Runtime gateway | `X-Agent-Api-Key` | Agent/tool-call ingress |
| Business APIs | `X-Internal-Service-Key` | Block direct sandbox API access |

In **production**, `AGENTSHIELD_AGENT_API_KEY` and `AGENTSHIELD_INTERNAL_SERVICE_KEY` are required. Development may omit them for local testing.

## Authorization

- **RBAC** enforced server-side via `require_permission()` (`app/core/rbac.py`)
- **Tenant isolation** via `org_filter()` and `assert_org_resource()` — cross-tenant resources return 404
- **Agent tool allowlists** enforced in `enforce_tool_call()` — models cannot bypass policy

## AI model boundary

Gemini/Vertex planners (`app/agents/`) recommend tool calls only. Final authorization always happens in `action_service.enforce_tool_call()`.

## Audit integrity

Audit events are hash-chained (`previous_event_hash` → `event_hash`). Verification helper: `app/services/audit_chain.py`.

## Reporting vulnerabilities

Do not open public issues for security reports. Contact your platform administrator or repository maintainer directly.
