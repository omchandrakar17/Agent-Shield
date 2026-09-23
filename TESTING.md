# AgentShield Testing Guide

## Backend unit & integration tests

```powershell
cd backend
pip install -e ".[dev]"
python -m pytest tests -q
```

Coverage includes policy/state machine, runtime gateway, auth, tenant isolation, RBAC, audit hash chain, cloud adapters, and agent planner flows.

## Frontend component tests

```powershell
cd frontend
npm ci
npm test
```

Vitest + Testing Library exercises the operations console with mocked API responses.

## End-to-end (Playwright)

E2E tests start the FastAPI backend and Vite frontend automatically.

```powershell
cd e2e
npm ci
npx playwright install chromium
npm test
```

Tests cover:

- Landing page
- Console agent demo (order lookup + prompt-injection block)
- Optional local-auth login flow (`E2E_AUTH_MODE=local` with backend `AGENTSHIELD_AUTH_MODE=local`)

## CI

GitHub Actions workflow `.github/workflows/ci.yml` runs backend pytest, frontend Vitest/build, and Playwright E2E on every push and pull request.
