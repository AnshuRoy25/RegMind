from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.api import ObligationOut
from app.services.obligation_service import obligation_service

router = APIRouter(prefix="/obligations", tags=["obligations"])


@router.get("/{obligation_id}", response_model=ObligationOut)
async def get_obligation(obligation_id: str) -> dict:
    row = await obligation_service.get(obligation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Obligation not found")
    return row


@router.get("", response_model=list[ObligationOut])
async def list_by_circular(circular_id: int) -> list[dict]:
    return await obligation_service.list_by_circular(circular_id)
