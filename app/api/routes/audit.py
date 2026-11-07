from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import AuditEventOut
from app.services.audit_service import audit_service

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventOut])
async def list_audit_events(limit: int = 200) -> list[dict]:
    rows = await audit_service.list(limit=min(max(limit, 1), 1000))
    return [
        {
            "id": row["id"],
            "actor": row["actor"],
            "action": row["action"],
            "ref_id": row["ref_id"],
            "detail": row["detail"],
            "created_at": row.get("at", ""),
        }
        for row in rows
    ]
