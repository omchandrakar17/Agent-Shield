"""Aggregate all v1 API routers."""

from fastapi import APIRouter

from app.api.v1 import (
    actions,
    agents,
    analytics,
    approvals,
    audit,
    auth_routes,
    business,
    controls,
    decisions,
    evaluations,
    events,
    executions,
    health,
    incidents,
    kill_switches,
    organizations,
    policies,
    replay,
    tools,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth_routes.router)
api_router.include_router(organizations.router)
api_router.include_router(analytics.router)
api_router.include_router(kill_switches.router)
api_router.include_router(controls.router)
api_router.include_router(policies.router)
api_router.include_router(actions.router)
api_router.include_router(approvals.router)
api_router.include_router(audit.router)
api_router.include_router(agents.router)
api_router.include_router(tools.router)
api_router.include_router(executions.router)
api_router.include_router(decisions.router)
api_router.include_router(replay.router)
api_router.include_router(incidents.router)
api_router.include_router(evaluations.router)
api_router.include_router(business.router)
api_router.include_router(events.router)
