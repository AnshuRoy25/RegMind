import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from regmind.app.models.base import Base, TimestampMixin, UUIDMixin


class ChangeSet(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "change_sets"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    circular_id: Mapped[int] = mapped_column(
        ForeignKey("circulars.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)


class ChangeTask(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "change_tasks"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    change_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("change_sets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    obligation_pk: Mapped[int | None] = mapped_column(
        "obligation_id",
        ForeignKey("obligations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    title: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    draft: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    draft_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    assignee: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
