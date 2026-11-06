from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)                       # TSK-001
    obligation_id: Mapped[str] = mapped_column(ForeignKey("obligations.id"), index=True)
    spec_summary: Mapped[str] = mapped_column(Text)
    evidence_checklist: Mapped[list[str]] = mapped_column(JSONB, default=list)
    urgency: Mapped[str] = mapped_column(String(20))
    assignee: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)         # open / ongoing / ...
    parent_task: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"))             # set for delta tasks
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )