"""FastAPI dependencies — auth, tenant, RBAC."""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import OperatorContext, get_current_operator
from app.core.rbac import Permission, role_has_permission
from app.database import get_db
from app.models import OrganizationModel


def get_operator(request: Request) -> OperatorContext:
    return get_current_operator(request)


OperatorDep = Depends(get_operator)


def require_permission(permission: Permission):
    def _checker(operator: OperatorContext = OperatorDep) -> OperatorContext:
        if not role_has_permission(operator.role, permission):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "FORBIDDEN",
                    "message": f"Role '{operator.role}' lacks permission '{permission.value}'",
                },
            )
        return operator

    return _checker


def get_organization(
    operator: OperatorContext = OperatorDep,
    db: Session = Depends(get_db),
) -> OrganizationModel:
    org = db.query(OrganizationModel).filter(OrganizationModel.id == operator.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail={"code": "ORG_NOT_FOUND", "message": "Organization not found"})
    return org
