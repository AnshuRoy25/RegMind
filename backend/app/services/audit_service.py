from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import AuditLog
from app.schemas import AuditLogRead


class AuditService:
    async def log(self, actor: str, action: str, ref_id: str, detail: dict) -> None:
        async with SessionLocal() as session:
            session.add(AuditLog(actor=actor, action=action, ref_id=ref_id, detail=detail or {}))
            await session.commit()

    # ---- used by the API, not by agents ----
    async def list_recent(self, ref_id: str | None = None, limit: int = 100) -> list[dict]:
        async with SessionLocal() as session:
            query = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
            if ref_id:
                query = query.where(AuditLog.ref_id == ref_id)
            rows = (await session.scalars(query)).all()
            result = []
            for row in rows:
                result.append(AuditLogRead.model_validate(row).model_dump(mode="json"))
            return result


audit_service = AuditService()