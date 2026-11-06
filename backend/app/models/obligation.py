from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

class Obligation(Base):
    __tablename__ = "obligations"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)             # OBL-001
    circular_id: Mapped[int] = mapped_column(ForeignKey("circulars.id"), index=True)
    section_ref: Mapped[str] = mapped_column(String(50), index=True)           # 3.1
    raw_text: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    actionable: Mapped[bool]
    category: Mapped[str] = mapped_column(String(20))                         # technical / business / ...
    urgency: Mapped[str | None] = mapped_column(String(20))                   # urgent / recurring / conditional
    approved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())