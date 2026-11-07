import uuid

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.obligation import Obligation
from app.models.task import Task
from app.services.common import iso, org_id_or_none


def _as_dict(row: Task, obligation_public_id: str) -> dict:
    return {
        "id": row.public_id,
        "obligation_id": obligation_public_id,
        "spec_summary": row.spec_summary,
        "evidence_checklist": list(row.evidence_checklist or []),
        "urgency": row.urgency,
        "assignee": row.assignee,
        "status": row.status,
        "parent_task": row.parent_task.public_id if row.parent_task else None,
        "pr_number": row.pr_number,
        "verification": dict(row.verification or {}),
        "created_at": iso(row.created_at),
        "updated_at": iso(row.updated_at),
    }


class SqlTaskService:
    async def create(
        self,
        obligation_id: str,
        spec_summary: str,
        checklist: list[str],
        urgency: str,
        assignee: str,
    ) -> str:
        db = SessionLocal()
        try:
            obligation = db.execute(
                select(Obligation).where(Obligation.public_id == obligation_id)
            ).scalar_one_or_none()
            if obligation is None:
                raise ValueError(f"No obligation {obligation_id}")
            row = Task(
                public_id=f"pending-{uuid.uuid4().hex[:8]}",
                org_id=org_id_or_none(),
                obligation_pk=obligation.id,
                spec_summary=spec_summary,
                evidence_checklist=list(checklist),
                urgency=urgency,
                assignee=assignee,
                status="open",
            )
            db.add(row)
            db.flush()
            row.public_id = f"TSK-{row.id:03d}"
            db.commit()
            return row.public_id
        finally:
            db.close()

    async def get(self, task_id: str) -> dict | None:
        db = SessionLocal()
        try:
            row = db.execute(
                select(Task, Obligation.public_id)
                .join(Obligation, Task.obligation_pk == Obligation.id)
                .where(Task.public_id == task_id)
            ).first()
            if row is None:
                return None
            task, obligation_public_id = row
            return _as_dict(task, obligation_public_id)
        finally:
            db.close()

    async def get_by_obligation(self, obligation_id: str) -> dict | None:
        db = SessionLocal()
        try:
            row = db.execute(
                select(Task, Obligation.public_id)
                .join(Obligation, Task.obligation_pk == Obligation.id)
                .where(
                    Obligation.public_id == obligation_id,
                    Task.status != "deprecated",
                )
                .order_by(Task.id.desc())
                .limit(1)
            ).first()
            if row is None:
                return None
            task, obligation_public_id = row
            return _as_dict(task, obligation_public_id)
        finally:
            db.close()

    async def set_status(self, task_id: str, status: str) -> None:
        db = SessionLocal()
        try:
            row = db.execute(
                select(Task).where(Task.public_id == task_id)
            ).scalar_one_or_none()
            if row is None:
                raise ValueError(f"No task {task_id}")
            row.status = status
            db.commit()
        finally:
            db.close()

    async def update_spec(self, task_id: str, spec_summary: str, checklist: list[str]) -> None:
        db = SessionLocal()
        try:
            row = db.execute(
                select(Task).where(Task.public_id == task_id)
            ).scalar_one_or_none()
            if row is None:
                raise ValueError(f"No task {task_id}")
            row.spec_summary = spec_summary
            row.evidence_checklist = list(checklist)
            db.commit()
        finally:
            db.close()

    async def create_delta(
        self, parent_id: str, spec_summary: str, checklist: list[str]
    ) -> str:
        db = SessionLocal()
        try:
            parent = db.execute(
                select(Task).where(Task.public_id == parent_id)
            ).scalar_one_or_none()
            if parent is None:
                raise ValueError(f"No task {parent_id}")
            row = Task(
                public_id=f"pending-{uuid.uuid4().hex[:8]}",
                org_id=parent.org_id,
                obligation_pk=parent.obligation_pk,
                parent_task_pk=parent.id,
                spec_summary=spec_summary,
                evidence_checklist=list(checklist),
                urgency=parent.urgency,
                assignee=parent.assignee,
                status="open",
            )
            db.add(row)
            db.flush()
            row.public_id = f"TSK-{row.id:03d}"
            db.commit()
            return row.public_id
        finally:
            db.close()

    async def list(self, limit: int = 100) -> list[dict]:
        db = SessionLocal()
        try:
            rows = db.execute(
                select(Task, Obligation.public_id)
                .join(Obligation, Task.obligation_pk == Obligation.id)
                .order_by(Task.id.desc())
                .limit(limit)
            ).all()
            return [_as_dict(task, obligation_public_id) for task, obligation_public_id in rows]
        finally:
            db.close()

    async def set_pr_number(self, task_id: str, pr_number: int) -> None:
        db = SessionLocal()
        try:
            row = db.execute(
                select(Task).where(Task.public_id == task_id)
            ).scalar_one_or_none()
            if row is None:
                raise ValueError(f"No task {task_id}")
            row.pr_number = pr_number
            db.commit()
        finally:
            db.close()

    async def record_verification(self, task_id: str, payload: dict) -> None:
        db = SessionLocal()
        try:
            row = db.execute(
                select(Task).where(Task.public_id == task_id)
            ).scalar_one_or_none()
            if row is None:
                raise ValueError(f"No task {task_id}")
            row.verification = payload
            db.commit()
        finally:
            db.close()


task_service = SqlTaskService()
