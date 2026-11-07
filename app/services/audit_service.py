from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.audit import AuditEvent
from app.services.common import iso, org_id_or_none


class SqlAuditService:
    async def log(self, actor: str, action: str, ref_id: str, detail: dict) -> None:
        db = SessionLocal()
        try:
            row = AuditEvent(
                org_id=org_id_or_none(),
                actor=actor,
                action=action,
                ref_id=str(ref_id),
                detail=detail or {},
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

    async def list(self, limit: int = 200) -> list[dict]:
        db = SessionLocal()
        try:
            rows = db.execute(
                select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
            ).scalars().all()
            return [
                {
                    "id": row.id,
                    "actor": row.actor,
                    "action": row.action,
                    "ref_id": row.ref_id,
                    "detail": row.detail,
                    "at": iso(row.created_at),
                }
                for row in rows
            ]
        finally:
            db.close()


audit_service = SqlAuditService()
