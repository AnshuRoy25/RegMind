import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from regmind.app.models.base import Base, TimestampMixin


class Obligation(TimestampMixin, Base):
    __tablename__ = "obligations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    circular_id: Mapped[int] = mapped_column(
        ForeignKey("circulars.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_ref: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    actionable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="informational", nullable=False)
    urgency: Mapped[str] = mapped_column(String(32), default="urgent", nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    approved_by: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    circular: Mapped["Circular"] = relationship(back_populates="obligations")
    tasks: Mapped[list["Task"]] = relationship(back_populates="obligation")
