from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from regmind.app.core.config import settings
from regmind.app.schemas.api import (
    ApproveCircularRequest,
    ApproveCircularResponse,
    CircularDetail,
    CircularSummary,
    CircularUploadResponse,
    ObligationOut,
)
from regmind.app.services.audit_service import audit_service
from regmind.app.services.circular_service import circular_service
from regmind.app.services.document_service import DocumentError, document_service
from regmind.app.services.obligation_service import obligation_service

router = APIRouter(prefix="/circulars", tags=["circulars"])


@router.get("", response_model=list[CircularSummary])
async def list_circulars(limit: int = 100) -> list[dict]:
    return await circular_service.list(limit=min(max(limit, 1), 500))


@router.get("/{circular_id}", response_model=CircularDetail)
async def get_circular(circular_id: int) -> dict:
    row = await circular_service.get(circular_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Circular not found")
    return row


@router.get("/{circular_id}/pages")
async def get_pages(circular_id: int) -> list[dict]:
    row = await circular_service.get(circular_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Circular not found")
    return await document_service.get_pages(circular_id)


@router.get("/{circular_id}/obligations", response_model=list[ObligationOut])
async def list_obligations(circular_id: int) -> list[dict]:
    row = await circular_service.get(circular_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Circular not found")
    return await obligation_service.list_by_circular(circular_id)


@router.post("/upload", response_model=CircularUploadResponse)
async def upload_circular(
    file: UploadFile = File(...),
    title: str = Form(""),
    kind: str = Form("master"),
    applies: bool = Form(True),
) -> dict:
    if kind not in ("master", "amendment"):
        raise HTTPException(status_code=400, detail="kind must be 'master' or 'amendment'")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File is larger than {settings.max_upload_mb} MB",
        )
    path = document_service.save_upload(file.filename or "circular.pdf", data)
    try:
        result = await document_service.ingest(
            path=path,
            title=title,
            kind=kind,
            applies=applies,
            source_filename=file.filename or path.name,
        )
    except DocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit_service.log(
        actor="regmind-api",
        action="circular_uploaded",
        ref_id=str(result["id"]),
        detail={
            "title": result["title"],
            "kind": kind,
            "pages": result["pages"],
            "ocr_used": result["ocr_used"],
        },
    )
    return result


@router.post("/{circular_id}/approve", response_model=ApproveCircularResponse)
async def approve_circular(
    circular_id: int, request: ApproveCircularRequest
) -> ApproveCircularResponse:
    row = await circular_service.get(circular_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Circular not found")
    approved = await obligation_service.approve_all(circular_id, request.approved_by)
    rows = await obligation_service.list_by_circular(circular_id)
    await audit_service.log(
        actor=request.approved_by or "regmind-api",
        action="obligations_approved",
        ref_id=str(circular_id),
        detail={"count": len(approved)},
    )
    technical = [
        item
        for item in rows
        if item["actionable"] and item["category"] == "technical"
    ]
    other = [
        item
        for item in rows
        if item["actionable"] and item["category"] != "technical"
    ]
    return ApproveCircularResponse(
        approved=approved,
        technical=technical,
        other_actionable=other,
    )
