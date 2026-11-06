from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import Task
from app.schemas import TaskRead


def _to_dict(row: Task) -> dict:
    return TaskRead.model_validate(row).model_dump(mode="json")


async def _next_id(session) -> str:
    count = await session.scalar(select(func.count()).select_from(Task))
    return f"TSK-{count + 1:03d}"


class TaskService:
    async def create(self, obligation_id: str, spec_summary: str, checklist: list[str],
                     urgency: str, assignee: str) -> str:
        async with SessionLocal() as session:
            task_id = await _next_id(session)
            session.add(Task(
                id=task_id, obligation_id=obligation_id, spec_summary=spec_summary,
                evidence_checklist=list(checklist), urgency=urgency, assignee=assignee, status="open",
            ))
            await session.commit()
            return task_id

    async def get(self, task_id: str) -> dict | None:
        async with SessionLocal() as session:
            row = await session.get(Task, task_id)
            return _to_dict(row) if row else None

    async def get_by_obligation(self, obligation_id: str) -> dict | None:
        """The live (not deprecated) task for this obligation, newest first."""
        async with SessionLocal() as session:
            query = (
                select(Task)
                .where(Task.obligation_id == obligation_id, Task.status != "deprecated")
                .order_by(Task.created_at.desc(), Task.id.desc())
                .limit(1)
            )
            row = await session.scalar(query)
            return _to_dict(row) if row else None

    async def set_status(self, task_id: str, status: str) -> None:
        async with SessionLocal() as session:
            row = await session.get(Task, task_id)
            row.status = status
            await session.commit()

    async def update_spec(self, task_id: str, spec_summary: str, checklist: list[str]) -> None:
        async with SessionLocal() as session:
            row = await session.get(Task, task_id)
            row.spec_summary = spec_summary
            row.evidence_checklist = list(checklist)
            await session.commit()

    async def create_delta(self, parent_id: str, spec_summary: str, checklist: list[str]) -> str:
        async with SessionLocal() as session:
            parent = await session.get(Task, parent_id)
            task_id = await _next_id(session)
            session.add(Task(
                id=task_id, obligation_id=parent.obligation_id, spec_summary=spec_summary,
                evidence_checklist=list(checklist), urgency=parent.urgency, assignee=parent.assignee,
                status="open", parent_task=parent_id,
            ))
            await session.commit()
            return task_id

    # ---- used by the API, not by agents ----
    async def list_all(self, status: str | None = None) -> list[dict]:
        async with SessionLocal() as session:
            query = select(Task).order_by(Task.id)
            if status:
                query = query.where(Task.status == status)
            rows = (await session.scalars(query)).all()
            result = []
            for row in rows:
                result.append(_to_dict(row))
            return result


task_service = TaskService()