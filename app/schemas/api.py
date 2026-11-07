from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    ok: bool
    database: str
    switch_configured: bool
    switch_supervisor_running: bool
    agents: int
    ocr_available: bool
    version: str


class CircularSummary(BaseModel):
    id: int
    title: str
    kind: str
    applies: bool
    status: str = ""
    received_at: str = ""


class CircularDetail(CircularSummary):
    raw_text: str = ""
    source_filename: str = ""
    source_path: str = ""


class CircularUploadResponse(BaseModel):
    id: int
    title: str
    kind: str
    applies: bool
    source_filename: str
    source_path: str
    pages: int
    ocr_used: bool
    chars: int
    sha256: str


class ObligationOut(BaseModel):
    id: str
    circular_id: int
    section_ref: str
    summary: str = ""
    raw_text: str = ""
    actionable: bool
    category: str
    urgency: str
    approved: bool
    approved_by: str = ""
    approved_at: str = ""
    created_at: str = ""


class ApproveCircularRequest(BaseModel):
    approved_by: str = Field(min_length=1, max_length=200)


class ApproveCircularResponse(BaseModel):
    ok: bool = True
    approved: list[str]
    technical: list[dict[str, Any]]
    other_actionable: list[dict[str, Any]]


class TaskOut(BaseModel):
    id: str
    obligation_id: str
    spec_summary: str = ""
    evidence_checklist: list[str] = []
    urgency: str
    assignee: str
    status: str
    parent_task: str | None = None
    pr_number: int | None = None
    verification: dict[str, Any] = {}
    created_at: str = ""
    updated_at: str = ""


class TaskCreate(BaseModel):
    obligation_id: str
    spec_summary: str
    evidence_checklist: list[str]
    urgency: str = "urgent"
    assignee: str = "engineer"


class TaskStatusUpdate(BaseModel):
    status: str


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    slug: str = ""


class DepartmentOut(BaseModel):
    id: str
    name: str
    slug: str
    description: str = ""
    is_active: bool = True
    approver_count: int = 0
    created_at: str = ""


class ApproverCreate(BaseModel):
    employee_id: str


class ApproverOut(BaseModel):
    department_id: str | None = None
    employee_id: str
    employee_name: str = ""
    name: str = ""
    email: str = ""
    role: str = ""
    created_at: str = ""
    added_at: str = ""


class PolicyEntryCreate(BaseModel):
    clause: str
    obligation: str
    control: str = ""
    owner: str = ""
    department_id: str | None = None
    obligation_id: str | None = None
    evidence_required: list[str] = []


class PolicyEntryOut(BaseModel):
    id: str
    clause: str
    obligation: str
    control: str = ""
    owner: str = ""
    status: str
    version: int
    department_id: str | None = None
    department: str = ""
    effective_date: str | None = None
    review_date: str | None = None
    evidence_required: list[str] = []
    created_at: str = ""
    updated_at: str = ""


class PolicyVersionCreate(BaseModel):
    control: str | None = None
    owner: str | None = None
    status: str | None = None
    approved_by: str = ""
    evidence_required: list[str] | None = None


class PolicyVersionOut(BaseModel):
    id: str
    version: int
    snapshot: dict[str, Any]
    approved_by: str = ""
    created_at: str = ""


class ChangeSetCreate(BaseModel):
    summary: str = ""
    department_map: dict[str, str] = {}


class ApprovalDecision(BaseModel):
    gate: str
    decision: str
    approver: str
    reason: str = ""
    employee_id: str | None = None


class AuditEventOut(BaseModel):
    id: int
    actor: str
    action: str
    ref_id: str
    detail: dict[str, Any]
    created_at: str


class SwitchProvisionRequest(BaseModel):
    install_discord: bool = True
    create_core_room: bool = True


class SwitchInstallRequest(BaseModel):
    platform: str = "discord"


class MessageResponse(BaseModel):
    ok: bool = True
    message: str = ""
    data: dict[str, Any] | None = None
