import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from regmind.app.models.base import Base, TimestampMixin


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    obligation_pk: Mapped[int] = mapped_column(
        "obligation_id",
        ForeignKey("obligations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_task_pk: Mapped[int | None] = mapped_column(
        "parent_task_id",
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    spec_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence_checklist: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    urgency: Mapped[str] = mapped_column(String(32), default="urgent", nullable=False)
    assignee: Mapped[str] = mapped_column(String(200), default="engineer", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False, index=True)
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verification: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    obligation: Mapped["Obligation"] = relationship(back_populates="tasks")
    parent_task: Mapped["Task | None"] = relationship(remote_side="Task.id")
