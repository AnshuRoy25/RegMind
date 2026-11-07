from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.approval import Approval
from app.models.change import ChangeSet, ChangeTask
from app.models.circular import Circular
from app.models.obligation import Obligation
from app.models.policy import PolicyEntry, PolicyVersion
from app.services.audit_service import audit_service
from app.services.common import ensure_default_organization, iso, utcnow
from app.services.department_service import department_service
from app.services.policy_service import _snapshot

CATEGORY_DEPARTMENTS = {
    "technical": "Engineering",
    "business": "Compliance",
    "prohibitive": "Compliance",
    "governance": "Compliance",
}


def _hash_draft(draft: dict) -> str:
    return hashlib.sha256(
        json.dumps(draft, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _task_dict(row: ChangeTask) -> dict:
    return {
        "id": str(row.id),
        "status": row.status,
        "title": row.title,
        "description": row.description,
        "draft": dict(row.draft or {}),
        "draft_hash": row.draft_hash,
        "assignee": row.assignee,
        "department_id": str(row.department_id) if row.department_id else None,
        "approved_at": iso(row.approved_at),
        "applied_at": iso(row.applied_at),
    }


def _set_dict(row: ChangeSet, tasks: list[ChangeTask]) -> dict:
    return {
        "id": str(row.id),
        "circular_id": row.circular_id,
        "status": row.status,
        "summary": row.summary,
        "created_at": iso(row.created_at),
        "tasks": [_task_dict(task) for task in tasks],
    }


class SqlChangeService:
    async def create_from_circular(
        self,
        circular_id: int,
        *,
        summary: str = "",
        department_map: dict[str, str] | None = None,
    ) -> dict:
        db = SessionLocal()
        try:
            circular = db.get(Circular, circular_id)
            if circular is None:
                raise ValueError(f"No circular with id {circular_id}")
            org = ensure_default_organization(db)
            obligations = db.execute(
                select(Obligation)
                .where(
                    Obligation.circular_id == circular_id,
                    Obligation.approved.is_(True),
                    Obligation.actionable.is_(True),
                )
                .order_by(Obligation.id.asc())
            ).scalars().all()
            if not obligations:
                raise ValueError(
                    "No approved actionable obligations found for this circular"
                )

            change_set = ChangeSet(
                org_id=org.id,
                circular_id=circular_id,
                status="pending_coe",
                summary=summary or f"Policy changes from {circular.title}",
            )
            db.add(change_set)
            db.flush()

            mapping = {**CATEGORY_DEPARTMENTS, **(department_map or {})}
            tasks: list[ChangeTask] = []
            for obligation in obligations:
                department_name = mapping.get(obligation.category)
                department = (
                    await department_service.get_or_create(db, org.id, department_name)
                    if department_name
                    else None
                )
                draft = {
                    "obligation_id": obligation.public_id,
                    "section_ref": obligation.section_ref,
                    "summary": obligation.summary,
                    "category": obligation.category,
                    "urgency": obligation.urgency,
                }
                task = ChangeTask(
                    org_id=org.id,
                    change_set_id=change_set.id,
                    department_id=department.id if department else None,
                    obligation_pk=obligation.id,
                    status="pending_coe",
                    title=obligation.summary[:300] or obligation.section_ref,
                    description=obligation.raw_text,
                    draft=draft,
                    draft_hash=_hash_draft(draft),
                    assignee="",
                )
                db.add(task)
                tasks.append(task)
            db.commit()
            for task in tasks:
                db.refresh(task)
            db.refresh(change_set)
            await audit_service.log(
                actor="regmind-api",
                action="change_set_created",
                ref_id=str(change_set.id),
                detail={
                    "circular_id": circular_id,
                    "tasks": len(tasks),
                    "departments": sorted(
                        {str(task.department_id) for task in tasks if task.department_id}
                    ),
                },
            )
            return _set_dict(change_set, tasks)
        finally:
            db.close()

    async def list(self, limit: int = 100) -> list[dict]:
        db = SessionLocal()
        try:
            rows = db.execute(
                select(ChangeSet).order_by(ChangeSet.created_at.desc()).limit(limit)
            ).scalars().all()
            result = []
            for row in rows:
                tasks = db.execute(
                    select(ChangeTask)
                    .where(ChangeTask.change_set_id == row.id)
                    .order_by(ChangeTask.created_at.asc())
                ).scalars().all()
                result.append(_set_dict(row, list(tasks)))
            return result
        finally:
            db.close()

    async def get(self, change_set_id: str) -> dict | None:
        db = SessionLocal()
        try:
            change_set = db.get(ChangeSet, uuid.UUID(change_set_id))
            if change_set is None:
                return None
            tasks = db.execute(
                select(ChangeTask)
                .where(ChangeTask.change_set_id == change_set.id)
                .order_by(ChangeTask.created_at.asc())
            ).scalars().all()
            result = _set_dict(change_set, list(tasks))
            approvals = db.execute(
                select(Approval)
                .where(Approval.change_set_id == change_set.id)
                .order_by(Approval.created_at.asc())
            ).scalars().all()
            result["approvals"] = [
                {
                    "id": str(row.id),
                    "gate": row.gate,
                    "decision": row.decision,
                    "approver": row.approver_platform_id,
                    "reason": row.reason,
                    "change_task_id": str(row.change_task_id) if row.change_task_id else None,
                    "created_at": iso(row.created_at),
                }
                for row in approvals
            ]
            return result
        finally:
            db.close()

    async def approve(
        self,
        change_set_id: str,
        *,
        gate: str,
        decision: str,
        approver: str,
        reason: str = "",
        employee_id: str | None = None,
    ) -> dict:
        if gate not in ("coe", "department"):
            raise ValueError("gate must be 'coe' or 'department'")
        if decision not in ("approved", "rejected"):
            raise ValueError("decision must be 'approved' or 'rejected'")
        db = SessionLocal()
        try:
            change_set = db.get(ChangeSet, uuid.UUID(change_set_id))
            if change_set is None:
                raise ValueError(f"No change set {change_set_id}")
            tasks = db.execute(
                select(ChangeTask).where(ChangeTask.change_set_id == change_set.id)
            ).scalars().all()
            if not tasks:
                raise ValueError("Change set has no tasks")

            approver_employee_id = uuid.UUID(employee_id) if employee_id else None
            if decision == "rejected":
                for task in tasks:
                    if task.status not in ("applied", "rejected"):
                        task.status = "rejected"
                    db.add(
                        Approval(
                            org_id=task.org_id,
                            change_set_id=change_set.id,
                            change_task_id=task.id,
                            gate=gate,
                            approver_employee_id=approver_employee_id,
                            approver_platform_id=approver,
                            decision="rejected",
                            reason=reason,
                            draft_hash=task.draft_hash,
                        )
                    )
                change_set.status = "rejected"
                db.commit()
                await audit_service.log(
                    actor=approver,
                    action="change_set_rejected",
                    ref_id=str(change_set.id),
                    detail={"gate": gate, "reason": reason},
                )
                return _set_dict(change_set, list(tasks))

            if gate == "coe":
                for task in tasks:
                    if task.status in ("applied", "rejected"):
                        continue
                    exists = db.execute(
                        select(Approval).where(
                            Approval.change_task_id == task.id,
                            Approval.gate == "coe",
                            Approval.decision == "approved",
                        )
                    ).first()
                    if exists:
                        continue
                    db.add(
                        Approval(
                            org_id=task.org_id,
                            change_set_id=change_set.id,
                            change_task_id=task.id,
                            gate="coe",
                            approver_employee_id=approver_employee_id,
                            approver_platform_id=approver,
                            decision="approved",
                            reason=reason,
                            draft_hash=task.draft_hash,
                        )
                    )
                    task.status = "pending_department"
                change_set.status = "pending_department"
                db.commit()
                await audit_service.log(
                    actor=approver,
                    action="change_set_coe_approved",
                    ref_id=str(change_set.id),
                    detail={"gate": gate, "reason": reason},
                )
                return _set_dict(change_set, list(tasks))

            missing_coe = []
            for task in tasks:
                if task.status in ("applied", "rejected"):
                    continue
                exists = db.execute(
                    select(Approval).where(
                        Approval.change_task_id == task.id,
                        Approval.gate == "coe",
                        Approval.decision == "approved",
                    )
                ).first()
                if not exists:
                    missing_coe.append(task.title)
            if missing_coe:
                raise ValueError(
                    "CoE approval is required first for: " + "; ".join(missing_coe[:5])
                )

            now = utcnow()
            for task in tasks:
                if task.status in ("applied", "rejected"):
                    continue
                db.add(
                    Approval(
                        org_id=task.org_id,
                        change_set_id=change_set.id,
                        change_task_id=task.id,
                        gate="department",
                        approver_employee_id=approver_employee_id,
                        approver_platform_id=approver,
                        decision="approved",
                        reason=reason,
                        draft_hash=task.draft_hash,
                    )
                )
                task.status = "applied"
                task.approved_at = now
                task.applied_at = now
                self._apply_policy(db, task)

            change_set.status = "applied"
            db.commit()
            await audit_service.log(
                actor=approver,
                action="change_set_applied",
                ref_id=str(change_set.id),
                detail={"gate": gate, "reason": reason, "tasks": len(tasks)},
            )
            return _set_dict(change_set, list(tasks))
        finally:
            db.close()

    @staticmethod
    def _apply_policy(db, task: ChangeTask) -> None:
        if task.obligation_pk is None:
            return
        obligation = db.get(Obligation, task.obligation_pk)
        if obligation is None:
            return
        entry = db.execute(
            select(PolicyEntry).where(
                PolicyEntry.org_id == task.org_id,
                PolicyEntry.obligation_pk == obligation.id,
            )
        ).scalar_one_or_none()
        evidence = list((task.draft or {}).get("evidence_checklist") or [])
        if entry is None:
            entry = PolicyEntry(
                org_id=task.org_id,
                department_id=task.department_id,
                obligation_pk=obligation.id,
                clause=obligation.section_ref,
                obligation=obligation.summary,
                control=task.description,
                owner=task.assignee,
                status="active",
                version=1,
                evidence_required=evidence,
            )
            db.add(entry)
            db.flush()
        else:
            entry.department_id = task.department_id or entry.department_id
            entry.clause = obligation.section_ref
            entry.obligation = obligation.summary
            entry.control = task.description or entry.control
            entry.owner = task.assignee or entry.owner
            entry.status = "active"
            entry.version += 1
            db.flush()
        db.add(
            PolicyVersion(
                policy_entry_id=entry.id,
                version=entry.version,
                snapshot=_snapshot(entry),
                approved_by="department",
            )
        )


change_service = SqlChangeService()


__all__ = ["CATEGORY_DEPARTMENTS", "SqlChangeService", "change_service"]
