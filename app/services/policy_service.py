from __future__ import annotations

import uuid

from sqlalchemy import select

from regmind.app.core.database import SessionLocal
from regmind.app.models.department import Department
from regmind.app.models.obligation import Obligation
from regmind.app.models.policy import PolicyEntry, PolicyVersion
from regmind.app.services.common import ensure_default_organization, iso


def _snapshot(row: PolicyEntry) -> dict:
    return {
        "id": str(row.id),
        "clause": row.clause,
        "obligation": row.obligation,
        "control": row.control,
        "owner": row.owner,
        "status": row.status,
        "version": row.version,
        "effective_date": row.effective_date.isoformat() if row.effective_date else None,
        "review_date": row.review_date.isoformat() if row.review_date else None,
        "evidence_required": list(row.evidence_required or []),
    }


def _as_dict(row: PolicyEntry, department_name: str = "") -> dict:
    return {**_snapshot(row), "department_id": str(row.department_id) if row.department_id else None,
            "department": department_name, "created_at": iso(row.created_at),
            "updated_at": iso(row.updated_at)}


class SqlPolicyService:
    async def list(self, limit: int = 200, status: str = "") -> list[dict]:
        db = SessionLocal()
        try:
            stmt = select(PolicyEntry, Department.name).outerjoin(
                Department, PolicyEntry.department_id == Department.id
            )
            if status:
                stmt = stmt.where(PolicyEntry.status == status)
            rows = db.execute(
                stmt.order_by(PolicyEntry.updated_at.desc()).limit(limit)
            ).all()
            return [_as_dict(entry, name or "") for entry, name in rows]
        finally:
            db.close()

    async def get(self, entry_id: str) -> dict | None:
        db = SessionLocal()
        try:
            row = db.get(PolicyEntry, uuid.UUID(entry_id))
            if row is None:
                return None
            department = db.get(Department, row.department_id) if row.department_id else None
            return _as_dict(row, department.name if department else "")
        finally:
            db.close()

    async def create(
        self,
        *,
        clause: str,
        obligation: str,
        control: str = "",
        owner: str = "",
        department_id: str | None = None,
        obligation_public_id: str | None = None,
        evidence_required: list[str] | None = None,
    ) -> dict:
        db = SessionLocal()
        try:
            org = ensure_default_organization(db)
            obligation_pk = None
            if obligation_public_id:
                obligation_row = db.execute(
                    select(Obligation).where(Obligation.public_id == obligation_public_id)
                ).scalar_one_or_none()
                if obligation_row is None:
                    raise ValueError(f"No obligation {obligation_public_id}")
                obligation_pk = obligation_row.id
            department_uuid = uuid.UUID(department_id) if department_id else None
            row = PolicyEntry(
                org_id=org.id,
                department_id=department_uuid,
                obligation_pk=obligation_pk,
                clause=clause,
                obligation=obligation,
                control=control,
                owner=owner,
                status="active",
                version=1,
                evidence_required=list(evidence_required or []),
            )
            db.add(row)
            db.flush()
            db.add(
                PolicyVersion(
                    policy_entry_id=row.id,
                    version=1,
                    snapshot=_snapshot(row),
                    approved_by=owner,
                )
            )
            db.commit()
            db.refresh(row)
            return _as_dict(row)
        finally:
            db.close()

    async def add_version(
        self,
        entry_id: str,
        *,
        control: str | None = None,
        owner: str | None = None,
        status: str | None = None,
        approved_by: str = "",
        evidence_required: list[str] | None = None,
    ) -> dict | None:
        db = SessionLocal()
        try:
            row = db.get(PolicyEntry, uuid.UUID(entry_id))
            if row is None:
                return None
            if control is not None:
                row.control = control
            if owner is not None:
                row.owner = owner
            if status is not None:
                row.status = status
            if evidence_required is not None:
                row.evidence_required = list(evidence_required)
            row.version += 1
            db.flush()
            db.add(
                PolicyVersion(
                    policy_entry_id=row.id,
                    version=row.version,
                    snapshot=_snapshot(row),
                    approved_by=approved_by,
                )
            )
            db.commit()
            db.refresh(row)
            return _as_dict(row)
        finally:
            db.close()

    async def versions(self, entry_id: str) -> list[dict]:
        db = SessionLocal()
        try:
            rows = db.execute(
                select(PolicyVersion)
                .where(PolicyVersion.policy_entry_id == uuid.UUID(entry_id))
                .order_by(PolicyVersion.version.desc())
            ).scalars().all()
            return [
                {
                    "id": str(row.id),
                    "version": row.version,
                    "snapshot": dict(row.snapshot or {}),
                    "approved_by": row.approved_by,
                    "created_at": iso(row.created_at),
                }
                for row in rows
            ]
        finally:
            db.close()


policy_service = SqlPolicyService()


__all__ = ["SqlPolicyService", "policy_service"]
