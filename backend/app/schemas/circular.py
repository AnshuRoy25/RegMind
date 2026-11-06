from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import CircularKind


class CircularCreate(BaseModel):
    """What regmind-intake saves after reading a circular."""
    title: str = Field(min_length=1, max_length=500)
    kind: CircularKind
    applies: bool
    raw_text: str = Field(min_length=1)


class CircularRead(BaseModel):
    """A stored circular, including its full text."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    kind: CircularKind
    applies: bool
    raw_text: str
    received_at: datetime


class CircularSummary(BaseModel):
    """A circular without its full text, for lists and API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    kind: CircularKind
    applies: bool
    received_at: datetime