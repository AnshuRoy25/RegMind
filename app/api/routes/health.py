from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select, text

from app.core.config import settings
from app.core.database import SessionLocal
from app.integrations.switch.supervisor import supervisor
from app.models.switch import SwitchAgent
from app.schemas.api import HealthResponse
from app.services.document_service import ocr_available

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    database = "ok"
    agents = 0
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        agents = int(
            db.execute(select(func.count(SwitchAgent.id))).scalar_one() or 0
        )
    except Exception as exc:
        database = f"error: {exc}"
    finally:
        db.close()

    return HealthResponse(
        ok=database == "ok",
        database=database,
        switch_configured=bool(settings.switch_url),
        switch_supervisor_running=supervisor.running,
        agents=agents,
        ocr_available=ocr_available(),
        version="0.1.0",
    )
