"""Organization and user management API."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import OperatorDep, require_permission
from app.auth import OperatorContext
from app.core.rbac import Permission
from app.database import get_db
from app.models import OrganizationMemberModel, OrganizationModel, UserModel

router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])


@router.get("/current")
def get_current_organization(
    operator: OperatorContext = OperatorDep,
    db: Session = Depends(get_db),
) -> dict:
    org = db.query(OrganizationModel).filter(OrganizationModel.id == operator.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail={"code": "ORG_NOT_FOUND", "message": "Organization not found"})
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "status": org.status,
        "plan": org.plan,
        "created_at": org.created_at,
    }


@router.get("/current/members")
def list_members(
    operator: OperatorContext = Depends(require_permission(Permission.USER_MANAGE)),
    db: Session = Depends(get_db),
) -> list[dict]:
    members = (
        db.query(OrganizationMemberModel, UserModel)
        .join(UserModel, UserModel.id == OrganizationMemberModel.user_id)
        .filter(OrganizationMemberModel.organization_id == operator.organization_id)
        .all()
    )
    return [
        {
            "user_id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": mem.role,
            "status": mem.status,
            "joined_at": mem.created_at,
        }
        for mem, user in members
    ]


class UpdateMemberRoleRequest(BaseModel):
    role: str = Field(min_length=3)


@router.patch("/current/members/{user_id}/role")
def update_member_role(
    user_id: str,
    body: UpdateMemberRoleRequest,
    operator: OperatorContext = Depends(require_permission(Permission.USER_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    mem = (
        db.query(OrganizationMemberModel)
        .filter(
            OrganizationMemberModel.organization_id == operator.organization_id,
            OrganizationMemberModel.user_id == user_id,
        )
        .first()
    )
    if not mem:
        raise HTTPException(status_code=404, detail={"code": "MEMBER_NOT_FOUND", "message": "Member not found"})
    mem.role = body.role
    db.commit()
    return {"user_id": user_id, "role": mem.role}
