import uuid
from datetime import timezone

from sqlalchemy import select

from regmind.app.core.database import SessionLocal
from regmind.app.models.circular import Circular
from regmind.app.models.obligation import Obligation
from regmind.app.services.common import iso, org_id_or_none, utcnow


def _as_dict(row: Obligation) -> dict:
    return {
        "id": row.public_id,
        "circular_id": row.circular_id,
        "section_ref": row.section_ref,
        "raw_text": row.raw_text,
        "summary": row.summary,
        "actionable": row.actionable,
        "category": row.category,
        "urgency": row.urgency,
        "approved": row.approved,
        "approved_by": row.approved_by,
        "approved_at": iso(row.approved_at),
        "created_at": iso(row.created_at),
    }


class SqlObligationService:
    async def save_many(self, circular_id: int, items: list[dict]) -> list[str]:
        db = SessionLocal()
        try:
            if db.get(Circular, circular_id) is None:
                raise ValueError(f"No circular with id {circular_id}")
            rows: list[Obligation] = []
            for item in items:
                row = Obligation(
                    public_id=f"pending-{uuid.uuid4().hex[:8]}",
                    org_id=org_id_or_none(),
                    circular_id=circular_id,
                    section_ref=str(item.get("section_ref", "")),
                    raw_text=str(item.get("raw_text", "")),
                    summary=str(item.get("summary", "")),
                    actionable=bool(item.get("actionable", False)),
                    category=str(item.get("category", "informational")),
                    urgency=str(item.get("urgency", "urgent")),
                    approved=bool(item.get("approved", False)),
                )
                db.add(row)
                rows.append(row)
            db.flush()
            for row in rows:
                row.public_id = f"OBL-{row.id:03d}"
            db.commit()
            return [row.public_id for row in rows]
        finally:
            db.close()

    async def get(self, obligation_id: str) -> dict | None:
        db = SessionLocal()
        try:
            row = db.execute(
                select(Obligation).where(Obligation.public_id == obligation_id)
            ).scalar_one_or_none()
            return _as_dict(row) if row else None
        finally:
            db.close()

    async def list_by_circular(self, circular_id: int) -> list[dict]:
        db = SessionLocal()
        try:
            rows = db.execute(
                select(Obligation)
                .where(Obligation.circular_id == circular_id)
                .order_by(Obligation.id.asc())
            ).scalars().all()
            return [_as_dict(row) for row in rows]
        finally:
            db.close()

    async def find_by_section(self, section_ref: str) -> dict | None:
        db = SessionLocal()
        try:
            row = db.execute(
                select(Obligation)
                .where(
                    Obligation.section_ref == section_ref,
                    Obligation.approved.is_(True),
                )
                .order_by(Obligation.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            return _as_dict(row) if row else None
        finally:
            db.close()

    async def approve_all(self, circular_id: int, approved_by: str = "") -> list[str]:
        db = SessionLocal()
        try:
            rows = db.execute(
                select(Obligation).where(
                    Obligation.circular_id == circular_id,
                    Obligation.approved.is_(False),
                )
            ).scalars().all()
            now = utcnow().astimezone(timezone.utc)
            for row in rows:
                row.approved = True
                row.approved_by = approved_by
                row.approved_at = now
            db.commit()
            return [row.public_id for row in rows]
        finally:
            db.close()


obligation_service = SqlObligationService()
