from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.api import (
    PolicyEntryCreate,
    PolicyEntryOut,
    PolicyVersionCreate,
    PolicyVersionOut,
)
from app.services.policy_service import policy_service

router = APIRouter(prefix="/policy", tags=["policy"])


@router.get("", response_model=list[PolicyEntryOut])
async def list_policy(status: str = "", limit: int = 200) -> list[dict]:
    return await policy_service.list(limit=min(max(limit, 1), 500), status=status)


@router.post("", response_model=PolicyEntryOut)
async def create_policy(request: PolicyEntryCreate) -> dict:
    try:
        return await policy_service.create(
            clause=request.clause,
            obligation=request.obligation,
            control=request.control,
            owner=request.owner,
            department_id=request.department_id,
            obligation_public_id=request.obligation_id,
            evidence_required=request.evidence_required,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{entry_id}", response_model=PolicyEntryOut)
async def get_policy(entry_id: str) -> dict:
    try:
        row = await policy_service.get(entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid policy id") from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Policy entry not found")
    return row


@router.get("/{entry_id}/versions", response_model=list[PolicyVersionOut])
async def list_versions(entry_id: str) -> list[dict]:
    try:
        return await policy_service.versions(entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid policy id") from exc


@router.post("/{entry_id}/versions", response_model=PolicyEntryOut)
async def add_version(entry_id: str, request: PolicyVersionCreate) -> dict:
    try:
        row = await policy_service.add_version(
            entry_id,
            control=request.control,
            owner=request.owner,
            status=request.status,
            approved_by=request.approved_by,
            evidence_required=request.evidence_required,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid policy id") from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Policy entry not found")
    return row
