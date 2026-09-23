"""Policy registry and lifecycle."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth import OperatorContext, OperatorDep
from app.core.http import api_error, get_request_id
from app.database import get_db
from app.models import PolicyModel
from app.policy_engine import ensure_default_policy, test_policy_rules
from app.schemas.requests import PolicyCreateRequest, PolicyTestRequest, PolicyUpdateRequest
from app.security import now
from app.services.audit_service import record_audit
from app.tenant import org_filter

router = APIRouter(prefix="/api/v1/policies", tags=["policies"])


@router.get("")
def get_policies(db: Session = Depends(get_db), operator: OperatorContext = OperatorDep) -> list[dict]:
    ensure_default_policy(db)
    policies = org_filter(
        db.query(PolicyModel).order_by(PolicyModel.version.desc()), PolicyModel, operator
    ).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "version": p.version,
            "status": p.status,
            "is_active": p.is_active,
            "published_at": p.published_at,
            "created_by": p.created_by,
            "rules": p.rules,
            "created_at": p.created_at,
        }
        for p in policies
    ]


@router.post("")
def create_policy(
    body: PolicyCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    operator: OperatorContext = OperatorDep,
) -> dict:
    req_id = get_request_id(request)
    existing = db.query(PolicyModel).filter(PolicyModel.id == body.id).order_by(PolicyModel.version.desc()).first()
    next_version = (existing.version + 1) if existing else 1
    new_policy = PolicyModel(
        id=f"{body.id}-v{next_version}" if existing else body.id,
        organization_id=operator.organization_id,
        name=body.name,
        version=next_version,
        status="DRAFT",
        is_active=False,
        published_at=None,
        created_by=body.created_by,
        rules=body.rules,
        created_at=now(),
    )
    db.add(new_policy)
    db.commit()
    db.refresh(new_policy)
    record_audit(
        db=db,
        event_type="POLICY_CREATED",
        action_id=None,
        approval_id=None,
        request_id=req_id,
        actor=body.created_by,
        data={"policy_id": new_policy.id, "version": new_policy.version, "status": "DRAFT"},
        organization_id=operator.organization_id,
    )
    return {
        "id": new_policy.id,
        "name": new_policy.name,
        "version": new_policy.version,
        "status": new_policy.status,
        "is_active": new_policy.is_active,
        "rules": new_policy.rules,
        "created_at": new_policy.created_at,
    }


@router.put("/{policy_id}")
def update_policy(
    policy_id: str,
    body: PolicyUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    operator: OperatorContext = OperatorDep,
) -> dict:
    req_id = get_request_id(request)
    pol = db.query(PolicyModel).filter(PolicyModel.id == policy_id).first()
    if not pol:
        raise api_error("POLICY_NOT_FOUND", f"Policy '{policy_id}' not found", req_id, 404)
    if pol.status == "PUBLISHED":
        raise api_error(
            "POLICY_VERSION_INVALID",
            f"Policy version '{pol.version}' is published and immutable. Create a new draft version instead.",
            req_id,
            409,
        )
    if body.name is not None:
        pol.name = body.name
    if body.rules is not None:
        pol.rules = body.rules
    db.commit()
    return {
        "id": pol.id,
        "name": pol.name,
        "version": pol.version,
        "status": pol.status,
        "rules": pol.rules,
    }


@router.post("/{policy_id}/publish")
def publish_policy(
    policy_id: str,
    request: Request,
    db: Session = Depends(get_db),
    operator: OperatorContext = OperatorDep,
) -> dict:
    req_id = get_request_id(request)
    pol = db.query(PolicyModel).filter(PolicyModel.id == policy_id).first()
    if not pol:
        raise api_error("POLICY_NOT_FOUND", f"Policy '{policy_id}' not found", req_id, 404)

    db.query(PolicyModel).filter(PolicyModel.status == "PUBLISHED").update({"status": "ARCHIVED", "is_active": False})
    pol.status = "PUBLISHED"
    pol.is_active = True
    pol.published_at = now()
    db.commit()

    record_audit(
        db=db,
        event_type="POLICY_PUBLISHED",
        action_id=None,
        approval_id=None,
        request_id=req_id,
        actor=operator.user_id,
        data={"policy_id": pol.id, "version": pol.version},
        organization_id=operator.organization_id,
    )
    return {
        "id": pol.id,
        "name": pol.name,
        "version": pol.version,
        "status": pol.status,
        "is_active": pol.is_active,
        "published_at": pol.published_at,
    }


@router.get("/{policy_id}/history")
def get_policy_history(policy_id: str, request: Request, db: Session = Depends(get_db)) -> list[dict]:
    base_prefix = policy_id.split("-v")[0]
    policies = db.query(PolicyModel).filter(PolicyModel.id.startswith(base_prefix)).order_by(PolicyModel.version.desc()).all()
    return [
        {"id": p.id, "version": p.version, "status": p.status, "published_at": p.published_at, "rules": p.rules}
        for p in policies
    ]


@router.post("/test")
def test_policy(body: PolicyTestRequest, request: Request, operator: OperatorContext = OperatorDep) -> dict:
    result = test_policy_rules(body.rules, body.action_type, body.target, body.payload)
    return {
        "decision": result["decision"],
        "matched_rule_id": result["matched_rule_id"],
        "risk_level": result["risk_level"],
        "reason": result["reason"],
    }
