import uuid

from sqlalchemy import Boolean, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from regmind.app.models.base import Base, TimestampMixin, UUIDMixin


class LLMConfig(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "llm_configs"
    __table_args__ = (UniqueConstraint("org_id", "role", name="uq_llm_config_org_role"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    provider: Mapped[str] = mapped_column(String(64), default="gemini", nullable=False)
    model: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    api_base: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    api_key_enc: Mapped[str] = mapped_column(Text, default="", nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
