from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import TaskStatus, UrgencyTier


class TaskCreate(BaseModel):
    """An engineering task created by regmind-spec for one technical obligation."""
    obligation_id: str = Field(examples=["OBL-003"])
    spec_summary: str = Field(min_length=1)
    evidence_checklist: list[str] = Field(min_length=1)
    urgency: UrgencyTier
    assignee: str = Field(min_length=1, max_length=100)


class DeltaTaskCreate(BaseModel):
    """A change task created by regmind-router when an amendment hits a shipped task."""
    parent_id: str = Field(examples=["TSK-001"])
    spec_summary: str = Field(min_length=1)
    evidence_checklist: list[str] = Field(min_length=1)


class TaskSpecUpdate(BaseModel):
    """New spec written by regmind-router after an amendment."""
    spec_summary: str = Field(min_length=1)
    evidence_checklist: list[str]


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskRead(BaseModel):
    """A stored task."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(examples=["TSK-001"])
    obligation_id: str
    spec_summary: str
    evidence_checklist: list[str]
    urgency: UrgencyTier
    assignee: str
    status: TaskStatus
    parent_task: str | None = None
    created_at: datetime
    updated_at: datetime