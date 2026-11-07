from __future__ import annotations

from fastapi import APIRouter, HTTPException

from regmind.app.core.config import settings
from regmind.app.core.database import SessionLocal
from regmind.app.integrations.switch.gateway import SwitchAPIError, get_gateway
from regmind.app.integrations.switch.provisioner import provision_workspace
from regmind.app.integrations.switch.agent_registry import registry
from regmind.app.integrations.switch.supervisor import supervisor
from regmind.app.models.switch import SwitchAgent, SwitchRoom, SwitchWorkspace
from regmind.app.schemas.api import MessageResponse, SwitchInstallRequest, SwitchProvisionRequest

router = APIRouter(prefix="/switch", tags=["switch"])


def _db_status() -> dict:
    db = SessionLocal()
    try:
        from sqlalchemy import select

        workspaces = db.execute(select(SwitchWorkspace)).scalars().all()
        agents = db.execute(select(SwitchAgent)).scalars().all()
        rooms = db.execute(select(SwitchRoom)).scalars().all()
        return {
            "workspaces": [
                {
                    "id": row.switch_workspace_id,
                    "name": row.name,
                    "organization_id": row.switch_tenant_id,
                }
                for row in workspaces
            ],
            "agents": [
                {
                    "id": row.switch_agent_id,
                    "chat_name": row.chat_name,
                    "role": str(row.role),
                    "connection_status": str(row.connection_status),
                    "last_connected_at": row.last_connected_at,
                }
                for row in agents
            ],
            "rooms": [
                {
                    "id": row.switch_room_id,
                    "name": row.name,
                    "kind": row.kind,
                    "department_id": str(row.department_id) if row.department_id else None,
                }
                for row in rooms
            ],
        }
    finally:
        db.close()


@router.get("/status")
async def status() -> dict:
    return {
        "configured": bool(settings.switch_url),
        "url": settings.switch_url,
        "supervisor": supervisor.status(),
        **_db_status(),
    }


@router.post("/provision")
async def provision(request: SwitchProvisionRequest) -> dict:
    try:
        return await provision_workspace(
            install_discord=request.install_discord,
            create_core_room=request.create_core_room,
        )
    except SwitchAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/start", response_model=MessageResponse)
async def start() -> MessageResponse:
    if not settings.switch_url:
        raise HTTPException(status_code=400, detail="SWITCH_URL is not configured")
    status_data = await supervisor.start()
    return MessageResponse(message="Switch supervisor started", data=status_data)


@router.post("/stop", response_model=MessageResponse)
async def stop() -> MessageResponse:
    await supervisor.stop()
    return MessageResponse(message="Switch supervisor stopped", data=supervisor.status())


@router.post("/reload", response_model=MessageResponse)
async def reload_agents() -> MessageResponse:
    await registry.refresh()
    return MessageResponse(
        message="Switch agent registry reloaded",
        data={"agents": list(registry.agents.keys())},
    )


@router.post("/install")
async def install(request: SwitchInstallRequest) -> dict:
    try:
        data = await get_gateway().begin_messaging_install(request.platform)
    except SwitchAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"platform": request.platform, "authorize_url": get_gateway().authorize_url(data)}
