from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import decrypt_secret, encrypt_secret
from app.integrations.switch.gateway import SwitchAPIError, get_gateway
from app.integrations.switch.protocol import register_agent
from app.models.organization import Organization
from app.models.switch import SwitchAgent, SwitchAgentRole, SwitchRoom, SwitchWorkspace
from app.services.audit_service import audit_service
from app.services.common import ensure_default_organization

log = logging.getLogger("regmind.switch.provisioner")

REGISTRATION_KEY_FILE = settings.storage_dir / "switch_registration_key"

AGENT_SPECS: list[dict[str, str]] = [
    {
        "chat_name": "regmind-intake",
        "display_name": "RegMind Intake",
        "role": SwitchAgentRole.INTAKE.value,
        "description": "Reads new SEBI circulars, decides whether they apply to the firm, and registers them.",
    },
    {
        "chat_name": "regmind-parser",
        "display_name": "RegMind Parser",
        "role": SwitchAgentRole.PARSER.value,
        "description": "Splits a master circular into clauses, classifies obligations, and handles officer approval.",
    },
    {
        "chat_name": "regmind-spec",
        "display_name": "RegMind Spec",
        "role": SwitchAgentRole.SPEC.value,
        "description": "Turns approved technical obligations into engineering tasks with evidence checklists.",
    },
    {
        "chat_name": "regmind-router",
        "display_name": "RegMind Router",
        "role": SwitchAgentRole.ROUTER.value,
        "description": "Applies amendment circulars to existing obligations and tasks.",
    },
    {
        "chat_name": "regmind-auditor",
        "display_name": "RegMind Auditor",
        "role": SwitchAgentRole.AUDITOR.value,
        "description": "Reviews pull requests against a task's evidence checklist and records verification.",
    },
]

CORE_ROOM_NAME = "Compliance Office"
CORE_ROOM_DESCRIPTION = "RegMind compliance team room. Share circulars here and mention an agent."


def _load_registration_key() -> str:
    if settings.switch_registration_key:
        return settings.switch_registration_key
    if REGISTRATION_KEY_FILE.exists():
        try:
            value = decrypt_secret(REGISTRATION_KEY_FILE.read_text(encoding="ascii").strip())
            if value:
                return value
        except (ValueError, OSError):
            log.exception("Could not read stored Switch registration key")
    return ""


def _save_registration_key(value: str) -> None:
    REGISTRATION_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    REGISTRATION_KEY_FILE.write_text(encrypt_secret(value), encoding="ascii")


async def _get_registration_key() -> str:
    key = _load_registration_key()
    if key:
        return key
    key = await get_gateway().create_registration_key()
    _save_registration_key(key)
    return key


def _workspace_row(
    db, org: Organization, workspace: dict[str, Any]
) -> SwitchWorkspace:
    workspace_id = str(workspace.get("id") or "")
    if not workspace_id:
        raise ValueError("Switch returned a workspace without an id")
    row = db.execute(
        select(SwitchWorkspace).where(SwitchWorkspace.org_id == org.id)
    ).scalar_one_or_none()
    if row is None:
        row = db.execute(
            select(SwitchWorkspace).where(
                SwitchWorkspace.switch_workspace_id == workspace_id
            )
        ).scalar_one_or_none()
    if row is None:
        row = SwitchWorkspace(
            org_id=org.id,
            switch_tenant_id=str(workspace.get("organization_id") or ""),
            switch_workspace_id=workspace_id,
            name=str(workspace.get("name") or settings.switch_workspace_name),
        )
        db.add(row)
    else:
        row.org_id = org.id
        row.switch_tenant_id = str(
            workspace.get("organization_id") or row.switch_tenant_id or ""
        )
        row.switch_workspace_id = workspace_id
        row.name = str(workspace.get("name") or row.name)
    db.flush()
    return row


def _ensure_agent_row(
    db,
    org: Organization,
    workspace: SwitchWorkspace,
    spec: dict[str, str],
    switch_agent_id: str,
    api_key: str,
) -> SwitchAgent:
    row = db.execute(
        select(SwitchAgent).where(
            SwitchAgent.org_id == org.id,
            SwitchAgent.chat_name == spec["chat_name"],
        )
    ).scalar_one_or_none()
    if row is None:
        row = SwitchAgent(
            org_id=org.id,
            workspace_id=workspace.id,
            switch_agent_id=switch_agent_id,
            role=SwitchAgentRole(spec["role"]),
            chat_name=spec["chat_name"],
            api_key_enc=encrypt_secret(api_key),
        )
        db.add(row)
    else:
        row.workspace_id = workspace.id
        row.switch_agent_id = switch_agent_id
        row.role = SwitchAgentRole(spec["role"])
        row.api_key_enc = encrypt_secret(api_key)
    db.flush()
    return row


def _ensure_room_row(
    db,
    org: Organization,
    workspace: SwitchWorkspace,
    switch_room_id: str,
    name: str,
    kind: str,
    purpose: str,
) -> SwitchRoom:
    row = db.execute(
        select(SwitchRoom).where(
            SwitchRoom.org_id == org.id,
            SwitchRoom.name == name,
        )
    ).scalar_one_or_none()
    if row is None:
        row = SwitchRoom(
            org_id=org.id,
            workspace_id=workspace.id,
            switch_room_id=switch_room_id,
            name=name,
            kind=kind,
            purpose=purpose,
        )
        db.add(row)
    else:
        row.workspace_id = workspace.id
        row.switch_room_id = switch_room_id
        row.kind = kind
        row.purpose = purpose
    db.flush()
    return row


async def provision_workspace(
    *,
    install_discord: bool = False,
    create_core_room: bool = True,
) -> dict[str, Any]:
    gateway = get_gateway()
    if not gateway.configured:
        raise ValueError("Switch is not configured (SWITCH_URL / SWITCH_EMAIL / SWITCH_PASSWORD)")

    ensured = await gateway.ensure_workspace(
        organization_name=settings.default_organization_name,
        workspace_name=settings.switch_workspace_name,
    )
    workspace = ensured["workspace"]
    switch_workspace_id = str(workspace.get("id") or "")
    if not switch_workspace_id:
        raise ValueError("Switch session did not resolve a workspace")

    db = SessionLocal()
    try:
        org = ensure_default_organization(db)
        workspace_row = _workspace_row(db, org, workspace)
        db.commit()
        org_id = org.id
        workspace_db_id = workspace_row.id
        workspace_name = workspace_row.name
        organization_id = workspace_row.switch_tenant_id
    finally:
        db.close()

    registration_key = await _get_registration_key()
    agents: list[dict[str, str]] = []
    switch_agent_ids: list[str] = []

    db = SessionLocal()
    try:
        org = db.get(Organization, org_id)
        workspace_row = db.get(SwitchWorkspace, workspace_db_id)
        if org is None or workspace_row is None:
            raise ValueError("Organization or workspace row disappeared")
        for spec in AGENT_SPECS:
            existing = db.execute(
                select(SwitchAgent).where(
                    SwitchAgent.org_id == org.id,
                    SwitchAgent.chat_name == spec["chat_name"],
                )
            ).scalar_one_or_none()
            if existing is not None and existing.api_key_enc:
                switch_agent_id = existing.switch_agent_id
                agents.append(
                    {
                        "chat_name": spec["chat_name"],
                        "switch_agent_id": switch_agent_id,
                        "status": "existing",
                    }
                )
            else:
                try:
                    result = await register_agent(
                        registration_key=registration_key,
                        name=spec["chat_name"],
                        display_name=spec["display_name"],
                        description=spec["description"],
                        models=[
                            {
                                "name": settings.gemini_model,
                                "description": "Google Gemini via Google ADK",
                            }
                        ],
                        metadata={"regmind_role": spec["role"]},
                    )
                except Exception as exc:
                    raise ValueError(
                        f"Could not register {spec['chat_name']}: {exc}. "
                        "If the name already exists, delete it in Switch Console or set "
                        "SWITCH_REGISTRATION_KEY to a valid registration key."
                    ) from exc
                switch_agent_id = str(result["id"])
                _ensure_agent_row(
                    db,
                    org,
                    workspace_row,
                    spec,
                    switch_agent_id,
                    str(result["api_key"]),
                )
                db.commit()
                agents.append(
                    {
                        "chat_name": spec["chat_name"],
                        "switch_agent_id": switch_agent_id,
                        "status": "registered",
                    }
                )

            switch_agent_ids.append(switch_agent_id)
            try:
                await gateway.set_addressing_open(switch_agent_id)
            except SwitchAPIError as exc:
                log.warning("Could not open addressing for %s: %s", spec["chat_name"], exc)
        db.commit()
    finally:
        db.close()

    rooms: list[dict[str, Any]] = []
    if create_core_room:
        existing_room_id = ""
        db = SessionLocal()
        try:
            existing_room = db.execute(
                select(SwitchRoom).where(
                    SwitchRoom.org_id == org_id,
                    SwitchRoom.name == CORE_ROOM_NAME,
                )
            ).scalar_one_or_none()
            if existing_room is not None:
                existing_room_id = existing_room.switch_room_id
        finally:
            db.close()

        if existing_room_id:
            switch_room_id = existing_room_id
            try:
                await gateway.add_room_agents(switch_room_id, switch_agent_ids)
            except SwitchAPIError as exc:
                log.warning("Could not refresh room agents for %s: %s", switch_room_id, exc)
            room_status = "existing"
        else:
            room = await gateway.create_room(
                name=CORE_ROOM_NAME,
                description=CORE_ROOM_DESCRIPTION,
                instructions=(
                    "This is the RegMind compliance office. Share a SEBI circular file and "
                    "mention @regmind-intake, or reply to an agent's approval request."
                ),
                agent_ids=switch_agent_ids,
            )
            switch_room_id = str(room.get("id") or room.get("transport_room_id") or "")
            if not switch_room_id:
                raise ValueError("Switch returned a room without an id")
            room_status = "created"

            db = SessionLocal()
            try:
                org = db.get(Organization, org_id)
                workspace_row = db.get(SwitchWorkspace, workspace_db_id)
                if org is None or workspace_row is None:
                    raise ValueError("Organization or workspace row disappeared")
                _ensure_room_row(
                    db,
                    org,
                    workspace_row,
                    switch_room_id,
                    CORE_ROOM_NAME,
                    "coe",
                    CORE_ROOM_DESCRIPTION,
                )
                db.commit()
            finally:
                db.close()

        rooms.append(
            {
                "name": CORE_ROOM_NAME,
                "switch_room_id": switch_room_id,
                "kind": "coe",
                "status": room_status,
            }
        )

    discord_authorize_url = ""
    discord_error = ""
    if install_discord:
        try:
            install = await gateway.begin_messaging_install("discord")
            discord_authorize_url = gateway.authorize_url(install)
        except Exception as exc:
            discord_error = str(exc)

    await audit_service.log(
        actor="regmind-api",
        action="switch_workspace_provisioned",
        ref_id=switch_workspace_id,
        detail={
            "workspace_name": workspace_name,
            "agents": len(agents),
            "rooms": len(rooms),
        },
    )

    return {
        "organization_id": organization_id,
        "workspace": {
            "id": switch_workspace_id,
            "name": workspace_name,
        },
        "agents": agents,
        "rooms": rooms,
        "discord_authorize_url": discord_authorize_url,
        "discord_error": discord_error,
    }


def registration_key_path() -> Path:
    return REGISTRATION_KEY_FILE


__all__ = ["AGENT_SPECS", "CORE_ROOM_NAME", "provision_workspace", "registration_key_path"]
