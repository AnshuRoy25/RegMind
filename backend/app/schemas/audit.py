from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditLogCreate(BaseModel):
    """One thing that happened, written by an agent tool."""
    actor: str = Field(examples=["regmind-router"])
    action: str = Field(examples=["amendment_applied"])
    ref_id: str = Field(examples=["TSK-001"])
    detail: dict[str, Any] = Field(default_factory=dict)


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor: str
    action: str
    ref_id: str
    detail: dict[str, Any]
    at: datetime