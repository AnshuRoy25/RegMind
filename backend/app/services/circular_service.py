from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Circular
from app.schemas import CircularRead, CircularSummary


class CircularService:
    async def save(self, title: str, kind: str, applies: bool, raw_text: str) -> int:
        async with SessionLocal() as session:
            row = Circular(title=title, kind=kind, applies=applies, raw_text=raw_text)
            session.add(row)
            await session.commit()
            return row.id

    async def get(self, circular_id: int) -> dict | None:
        async with SessionLocal() as session:
            row = await session.get(Circular, circular_id)
            if row is None:
                return None
            return CircularRead.model_validate(row).model_dump(mode="json")

    # ---- used by the API, not by agents ----
    async def list_all(self) -> list[dict]:
        async with SessionLocal() as session:
            rows = (await session.scalars(select(Circular).order_by(Circular.id))).all()
            result = []
            for row in rows:
                result.append(CircularSummary.model_validate(row).model_dump(mode="json"))
            return result


circular_service = CircularService()