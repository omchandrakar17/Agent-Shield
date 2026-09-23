"""Internal sandbox business APIs — not for direct agent access."""

from fastapi import APIRouter

from app.business_tools import execute_business_tool
from app.runtime.auth import InternalServiceDep

router = APIRouter(prefix="/api/v1/business", tags=["business"])


@router.get("/orders/{order_id}")
def business_get_order(order_id: str, _internal: object = InternalServiceDep) -> dict:
    return execute_business_tool("get_order", f"order:{order_id}", {"include_shipping": True})


@router.get("/customers/{customer_id}")
def business_get_customer(customer_id: str, _internal: object = InternalServiceDep) -> dict:
    return execute_business_tool("get_customer", f"customer:{customer_id}", {"customer_id": customer_id})


@router.get("/policies/refunds")
def business_refund_policy(_internal: object = InternalServiceDep) -> dict:
    return execute_business_tool("search_refund_policy", "policy:refunds", {})


@router.post("/refunds")
def business_issue_refund(payload: dict, _internal: object = InternalServiceDep) -> dict:
    order_id = payload.get("order_id", "2481")
    return execute_business_tool("issue_refund", f"order:{order_id}", payload)
