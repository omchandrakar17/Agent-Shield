"""Tenant scoping helpers — server-side organization isolation."""

from sqlalchemy.orm import Query, Session

from app.auth import OperatorContext


def org_filter(query: Query, model, operator: OperatorContext) -> Query:
    """Restrict query to the operator's organization unless platform admin."""
    if operator.role == "PLATFORM_ADMIN":
        return query
    if hasattr(model, "organization_id"):
        return query.filter(model.organization_id == operator.organization_id)
    return query


def assert_org_resource(resource_org_id: str | None, operator: OperatorContext) -> None:
    from fastapi import HTTPException

    if operator.role == "PLATFORM_ADMIN":
        return
    if resource_org_id != operator.organization_id:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Resource not found"},
        )


def default_org_id(operator: OperatorContext) -> str:
    return operator.organization_id
