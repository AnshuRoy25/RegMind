from app.core.database import SessionLocal
from app.models.circular import Circular
from app.services.common import iso, org_id_or_none


class SqlCircularService:
    async def save(self, title: str, kind: str, applies: bool, raw_text: str) -> int:
        db = SessionLocal()
        try:
            row = Circular(
                org_id=org_id_or_none(),
                title=title,
                kind=kind,
                applies=applies,
                raw_text=raw_text,
                status="registered",
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row.id
        finally:
            db.close()

    async def get(self, circular_id: int) -> dict | None:
        db = SessionLocal()
        try:
            row = db.get(Circular, circular_id)
            if row is None:
                return None
            return {
                "id": row.id,
                "title": row.title,
                "kind": row.kind,
                "applies": row.applies,
                "raw_text": row.raw_text,
                "received_at": iso(row.received_at),
                "source_filename": row.source_filename,
                "source_path": row.source_path,
                "status": row.status,
            }
        finally:
            db.close()

    async def list(self, limit: int = 100) -> list[dict]:
        from sqlalchemy import select

        db = SessionLocal()
        try:
            rows = db.execute(
                select(Circular).order_by(Circular.id.desc()).limit(limit)
            ).scalars().all()
            return [
                {
                    "id": row.id,
                    "title": row.title,
                    "kind": row.kind,
                    "applies": row.applies,
                    "status": row.status,
                    "received_at": iso(row.received_at),
                }
                for row in rows
            ]
        finally:
            db.close()


circular_service = SqlCircularService()
