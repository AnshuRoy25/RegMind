from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select

from regmind.app.core.database import SessionLocal
from regmind.app.models.department import Department, DepartmentApprover
from regmind.app.models.organization import Employee
from regmind.app.services.common import ensure_default_organization, iso, utcnow


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "department"


def _as_dict(row: Department, approver_count: int = 0) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "slug": row.slug,
        "description": row.description,
        "is_active": row.is_active,
        "approver_count": approver_count,
        "created_at": iso(row.created_at),
    }


class SqlDepartmentService:
    async def list(self, limit: int = 100) -> list[dict]:
        db = SessionLocal()
        try:
            rows = db.execute(
                select(Department).order_by(Department.name.asc()).limit(limit)
            ).scalars().all()
            counts = dict(
                db.execute(
                    select(
                        DepartmentApprover.department_id,
                        func.count(DepartmentApprover.id),
                    ).group_by(DepartmentApprover.department_id)
                ).all()
            )
            return [_as_dict(row, counts.get(row.id, 0)) for row in rows]
        finally:
            db.close()

    async def get(self, department_id: str) -> dict | None:
        db = SessionLocal()
        try:
            row = db.get(Department, uuid.UUID(department_id))
            if row is None:
                return None
            return _as_dict(row, len(row.approvers))
        finally:
            db.close()

    async def create(
        self, name: str, description: str = "", slug: str = ""
    ) -> dict:
        db = SessionLocal()
        try:
            org = ensure_default_organization(db)
            slug = slugify(slug or name)
            existing = db.execute(
                select(Department).where(
                    Department.org_id == org.id, Department.slug == slug
                )
            ).scalar_one_or_none()
            if existing is not None:
                if description:
                    existing.description = description
                db.commit()
                return _as_dict(existing, len(existing.approvers))
            row = Department(
                org_id=org.id,
                name=name.strip(),
                slug=slug,
                description=description.strip(),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return _as_dict(row)
        finally:
            db.close()

    async def get_or_create(self, db, org_id: uuid.UUID, name: str) -> Department:
        slug = slugify(name)
        row = db.execute(
            select(Department).where(
                Department.org_id == org_id, Department.slug == slug
            )
        ).scalar_one_or_none()
        if row is None:
            row = Department(
                org_id=org_id,
                name=name.strip().title(),
                slug=slug,
                description=f"{name.strip().title()} department",
            )
            db.add(row)
            db.flush()
        return row

    async def add_approver(
        self, department_id: str, employee_id: str
    ) -> dict:
        db = SessionLocal()
        try:
            department = db.get(Department, uuid.UUID(department_id))
            if department is None:
                raise ValueError(f"No department {department_id}")
            employee = db.get(Employee, uuid.UUID(employee_id))
            if employee is None:
                raise ValueError(f"No employee {employee_id}")
            existing = db.execute(
                select(DepartmentApprover).where(
                    DepartmentApprover.department_id == department.id,
                    DepartmentApprover.employee_id == employee.id,
                )
            ).scalar_one_or_none()
            if existing is None:
                existing = DepartmentApprover(
                    department_id=department.id, employee_id=employee.id
                )
                db.add(existing)
                db.commit()
            return {
                "department_id": str(department.id),
                "employee_id": str(employee.id),
                "employee_name": employee.name,
                "created_at": iso(existing.created_at),
            }
        finally:
            db.close()

    async def list_approvers(self, department_id: str) -> list[dict]:
        db = SessionLocal()
        try:
            rows = db.execute(
                select(DepartmentApprover, Employee)
                .join(Employee, DepartmentApprover.employee_id == Employee.id)
                .where(DepartmentApprover.department_id == uuid.UUID(department_id))
                .order_by(Employee.name.asc())
            ).all()
            return [
                {
                    "employee_id": str(employee.id),
                    "name": employee.name,
                    "email": employee.email,
                    "role": str(employee.role),
                    "added_at": iso(link.created_at),
                }
                for link, employee in rows
            ]
        finally:
            db.close()


department_service = SqlDepartmentService()


__all__ = ["SqlDepartmentService", "department_service", "slugify"]
