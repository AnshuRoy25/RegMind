from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import ObligationCategory, UrgencyTier


class ObligationCreate(BaseModel):
    """One clause of a circular, classified by regmind-parser (or added by regmind-router)."""
    section_ref: str = Field(min_length=1, max_length=50, examples=["3.1"])
    raw_text: str
    summary: str
    actionable: bool
    category: ObligationCategory
    urgency: UrgencyTier | None = None


class ObligationRead(BaseModel):
    """A stored obligation."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(examples=["OBL-001"])
    circular_id: int
    section_ref: str
    raw_text: str
    summary: str
    actionable: bool
    category: ObligationCategory
    urgency: UrgencyTier | None
    approved: bool
    created_at: datetime