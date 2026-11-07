import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from regmind.app.models.base import Base, TimestampMixin, UUIDMixin


class Approval(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "approvals"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    change_set_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("change_sets.id", ondelete="CASCADE"), nullable=True, index=True
    )
    change_task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("change_tasks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    gate: Mapped[str] = mapped_column(String(32), default="coe", nullable=False)
    approver_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    approver_platform_id: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    decision: Mapped[str] = mapped_column(String(32), default="approved", nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    draft_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    discord_message_id: Mapped[str] = mapped_column(String(128), default="", nullable=False)
