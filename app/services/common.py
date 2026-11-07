from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.core.context import current_org_id
from app.core.database import SessionLocal
from app.models.organization import Organization


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat()


def org_id_or_none() -> Any:
    return current_org_id.get()


def default_organization(db) -> Organization | None:
    row = db.execute(select(Organization).order_by(Organization.created_at.asc()).limit(1)).scalar_one_or_none()
    return row


def ensure_default_organization(db) -> Organization:
    row = default_organization(db)
    if row is not None:
        return row
    from app.core.config import settings

    row = Organization(
        name=settings.default_organization_name,
        slug=settings.default_organization_slug,
    )
    db.add(row)
    db.flush()
    return row


def session():
    return SessionLocal()
