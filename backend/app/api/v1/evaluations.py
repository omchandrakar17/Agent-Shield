"""Evaluation lab."""

from fastapi import APIRouter, Depends, Request

from app.auth import OperatorContext, OperatorDep
from app.evaluation import load_eval_cases, run_evaluation

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


@router.post("/run")
def run_eval(request: Request, operator: OperatorContext = OperatorDep) -> dict:
    from fastapi.testclient import TestClient
    from app.main import app

    return run_evaluation(TestClient(app))


@router.get("/summary")
def eval_summary(operator: OperatorContext = OperatorDep) -> dict:
    cases = load_eval_cases()
    categories: dict[str, int] = {}
    for c in cases:
        cat = c.get("category", "general")
        categories[cat] = categories.get(cat, 0) + 1
    return {"total_cases": len(cases), "categories": categories}
