import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Circular(TimestampMixin, Base):
    __tablename__ = "circulars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    applies: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    source_filename: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    source_path: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    mimetype: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="registered", nullable=False)
    regulator: Mapped[str] = mapped_column(String(200), default="SEBI", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)

    obligations: Mapped[list["Obligation"]] = relationship(
        back_populates="circular", cascade="all, delete-orphan"
    )


class CircularPage(TimestampMixin, Base):
    __tablename__ = "circular_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    circular_id: Mapped[int] = mapped_column(
        ForeignKey("circulars.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confidence: Mapped[float] = mapped_column(default=0.0, nullable=False)

    circular: Mapped["Circular"] = relationship()

