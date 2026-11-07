from __future__ import annotations

from fastapi import APIRouter, HTTPException

from regmind.app.schemas.api import ApprovalDecision, ChangeSetCreate
from regmind.app.services.change_service import change_service

router = APIRouter(prefix="/changes", tags=["changes"])


@router.get("")
async def list_change_sets(limit: int = 100) -> list[dict]:
    return await change_service.list(limit=min(max(limit, 1), 500))


@router.post("/from-circular/{circular_id}")
async def create_change_set(circular_id: int, request: ChangeSetCreate) -> dict:
    try:
        return await change_service.create_from_circular(
            circular_id,
            summary=request.summary,
            department_map=request.department_map,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{change_set_id}")
async def get_change_set(change_set_id: str) -> dict:
    try:
        row = await change_service.get(change_set_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid change set id") from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Change set not found")
    return row


@router.post("/{change_set_id}/approve")
async def approve_change_set(
    change_set_id: str, request: ApprovalDecision
) -> dict:
    try:
        return await change_service.approve(
            change_set_id,
            gate=request.gate,
            decision=request.decision,
            approver=request.approver,
            reason=request.reason,
            employee_id=request.employee_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
