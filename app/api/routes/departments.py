from __future__ import annotations

from fastapi import APIRouter, HTTPException

from regmind.app.schemas.api import ApproverCreate, ApproverOut, DepartmentCreate, DepartmentOut
from regmind.app.services.department_service import department_service

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentOut])
async def list_departments(limit: int = 100) -> list[dict]:
    return await department_service.list(limit=min(max(limit, 1), 500))


@router.post("", response_model=DepartmentOut)
async def create_department(request: DepartmentCreate) -> dict:
    return await department_service.create(
        name=request.name,
        description=request.description,
        slug=request.slug,
    )


@router.get("/{department_id}", response_model=DepartmentOut)
async def get_department(department_id: str) -> dict:
    try:
        row = await department_service.get(department_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid department id") from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Department not found")
    return row


@router.get("/{department_id}/approvers", response_model=list[ApproverOut])
async def list_approvers(department_id: str) -> list[dict]:
    try:
        return await department_service.list_approvers(department_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid department id") from exc


@router.post("/{department_id}/approvers", response_model=ApproverOut)
async def add_approver(department_id: str, request: ApproverCreate) -> dict:
    try:
        return await department_service.add_approver(department_id, request.employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
