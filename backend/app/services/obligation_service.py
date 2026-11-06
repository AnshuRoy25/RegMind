from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import Obligation
from app.schemas import ObligationRead


def _to_dict(row: Obligation) -> dict:
    return ObligationRead.model_validate(row).model_dump(mode="json")


class ObligationService:
    async def save_many(self, circular_id: int, items: list[dict]) -> list[str]:
        async with SessionLocal() as session:
            count = await session.scalar(select(func.count()).select_from(Obligation))
            ids = []
            for item in items:
                count += 1
                obligation_id = f"OBL-{count:03d}"
                session.add(Obligation(
                    id=obligation_id,
                    circular_id=circular_id,
                    section_ref=item.get("section_ref", ""),
                    raw_text=item.get("raw_text", ""),
                    summary=item.get("summary", ""),
                    actionable=bool(item.get("actionable", False)),
                    category=item.get("category", "informational"),
                    urgency=item.get("urgency"),
                ))
                ids.append(obligation_id)
            await session.commit()
            return ids

    async def get(self, obligation_id: str) -> dict | None:
        async with SessionLocal() as session:
            row = await session.get(Obligation, obligation_id)
            return _to_dict(row) if row else None

    async def list_by_circular(self, circular_id: int) -> list[dict]:
        async with SessionLocal() as session:
            query = select(Obligation).where(Obligation.circular_id == circular_id).order_by(Obligation.id)
            rows = (await session.scalars(query)).all()
            result = []
            for row in rows:
                result.append(_to_dict(row))
            return result

    async def find_by_section(self, section_ref: str) -> dict | None:
        """Newest approved obligation with this section reference."""
        async with SessionLocal() as session:
            query = (
                select(Obligation)
                .where(Obligation.section_ref == section_ref, Obligation.approved.is_(True))
                .order_by(Obligation.created_at.desc(), Obligation.id.desc())
                .limit(1)
            )
            row = await session.scalar(query)
            return _to_dict(row) if row else None

    async def approve_all(self, circular_id: int) -> list[str]:
        async with SessionLocal() as session:
            query = select(Obligation).where(Obligation.circular_id == circular_id, Obligation.approved.is_(False))
            rows = (await session.scalars(query)).all()
            ids = []
            for row in rows:
                row.approved = True
                ids.append(row.id)
            await session.commit()
            return ids

    # ---- used by the API, not by agents ----
    async def list_all(self) -> list[dict]:
        async with SessionLocal() as session:
            rows = (await session.scalars(select(Obligation).order_by(Obligation.id))).all()
            result = []
            for row in rows:
                result.append(_to_dict(row))
            return result


obligation_service = ObligationService()