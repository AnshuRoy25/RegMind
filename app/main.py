from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from regmind.app.api.router import api_router
from regmind.app.core.config import settings
from regmind.app.core.context import current_org_id
from regmind.app.core.database import SessionLocal
from regmind.app.integrations.switch.agent_registry import registry
from regmind.app.integrations.switch.gateway import close_gateway
from regmind.app.integrations.switch.supervisor import supervisor
from regmind.app.services.common import ensure_default_organization

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("regmind")


def _ensure_org() -> None:
    db = SessionLocal()
    try:
        ensure_default_organization(db)
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        _ensure_org()
    except Exception:
        log.exception("Could not ensure the default organization at startup")

    if settings.switch_autoconnect and settings.switch_url:
        log.info("Starting Switch supervisor")
        await supervisor.start()

    yield

    await supervisor.stop()
    await registry.close()
    await close_gateway()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="RegMind compliance backend: circulars, obligations, tasks, policy and Switch agents.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def organization_context(request, call_next):
    token = current_org_id.set(None)
    org_token = None
    try:
        try:
            db = SessionLocal()
            try:
                org = ensure_default_organization(db)
                db.commit()
                org_token = current_org_id.set(org.id)
            finally:
                db.close()
        except Exception:
            log.exception("Could not set organization context")
        return await call_next(request)
    finally:
        if org_token is not None:
            current_org_id.reset(org_token)
        current_org_id.reset(token)


app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/", tags=["health"])
async def index() -> dict:
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
        "api": settings.api_prefix,
        "switch_configured": bool(settings.switch_url),
        "switch_supervisor_running": supervisor.running,
    }


__all__ = ["app"]
