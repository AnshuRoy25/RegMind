import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from regmind.app.models.base import Base, TimestampMixin, UUIDMixin


class PolicyEntry(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "policy_entries"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
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
    clause: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    obligation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    control: Mapped[str] = mapped_column(Text, default="", nullable=False)
    owner: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    evidence_required: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)


class PolicyVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "policy_versions"
    __table_args__ = (
        UniqueConstraint("policy_entry_id", "version", name="uq_policy_version"),
    )

    policy_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("policy_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    approved_by: Mapped[str] = mapped_column(String(200), default="", nullable=False)
