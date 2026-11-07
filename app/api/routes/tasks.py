from __future__ import annotations

from fastapi import APIRouter, HTTPException

from regmind.app.agents.contracts import TASK_STATUSES, URGENCY_TIERS
from regmind.app.schemas.api import TaskCreate, TaskOut, TaskStatusUpdate
from regmind.app.services.audit_service import audit_service
from regmind.app.services.task_service import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskOut])
async def list_tasks(limit: int = 100) -> list[dict]:
    return await task_service.list(limit=min(max(limit, 1), 500))


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: str) -> dict:
    row = await task_service.get(task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return row


@router.post("", response_model=TaskOut)
async def create_task(request: TaskCreate) -> dict:
    if not request.evidence_checklist:
        raise HTTPException(status_code=400, detail="evidence_checklist must not be empty")
    if request.urgency not in URGENCY_TIERS:
        raise HTTPException(
            status_code=400,
            detail=f"urgency must be one of {list(URGENCY_TIERS)}",
        )
    try:
        task_id = await task_service.create(
            request.obligation_id,
            request.spec_summary,
            request.evidence_checklist,
            request.urgency,
            request.assignee,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    row = await task_service.get(task_id)
    if row is None:
        raise HTTPException(status_code=500, detail="Task was created but could not be read")
    await audit_service.log(
        actor="regmind-api",
        action="task_created",
        ref_id=task_id,
        detail={"obligation_id": request.obligation_id, "urgency": request.urgency},
    )
    return row


@router.patch("/{task_id}/status", response_model=TaskOut)
async def set_status(task_id: str, request: TaskStatusUpdate) -> dict:
    if request.status not in TASK_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {list(TASK_STATUSES)}",
        )
    try:
        await task_service.set_status(task_id, request.status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    row = await task_service.get(task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return row
