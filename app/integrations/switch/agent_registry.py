from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select

from regmind.app.core.database import SessionLocal
from regmind.app.core.security import decrypt_secret
from regmind.app.models.switch import SwitchAgent, SwitchConnectionStatus
from regmind.app.integrations.switch.protocol import SwitchProtocolClient

log = logging.getLogger("regmind.switch.registry")


@dataclass
class RegisteredAgent:
    db_id: uuid.UUID
    org_id: uuid.UUID
    switch_agent_id: str
    chat_name: str
    role: str
    api_key: str
    department_id: uuid.UUID | None = None
    client: SwitchProtocolClient = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.client = SwitchProtocolClient(self.switch_agent_id, self.api_key)


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, RegisteredAgent] = {}
        self._lock = asyncio.Lock()

    @property
    def agents(self) -> dict[str, RegisteredAgent]:
        return dict(self._agents)

    def get(self, chat_name: str) -> RegisteredAgent | None:
        return self._agents.get(chat_name)

    def supervisor_agent(self) -> RegisteredAgent | None:
        preferred = self._agents.get("regmind-intake")
        if preferred is not None:
            return preferred
        for agent in self._agents.values():
            if agent.role == "intake":
                return agent
        return next(iter(self._agents.values()), None)

    def for_org(self, org_id: uuid.UUID) -> list[RegisteredAgent]:
        return [agent for agent in self._agents.values() if agent.org_id == org_id]

    async def refresh(self) -> None:
        async with self._lock:
            rows: list[RegisteredAgent] = []
            db = SessionLocal()
            try:
                records = db.execute(
                    select(SwitchAgent).order_by(SwitchAgent.created_at.asc())
                ).scalars().all()
                for record in records:
                    if not record.api_key_enc:
                        continue
                    try:
                        api_key = decrypt_secret(record.api_key_enc)
                    except ValueError:
                        log.exception("Could not decrypt API key for %s", record.chat_name)
                        continue
                    if not api_key:
                        continue
                    rows.append(
                        RegisteredAgent(
                            db_id=record.id,
                            org_id=record.org_id,
                            switch_agent_id=record.switch_agent_id,
                            chat_name=record.chat_name,
                            role=str(record.role),
                            api_key=api_key,
                            department_id=record.department_id,
                        )
                    )
            finally:
                db.close()

            new_map = {agent.chat_name: agent for agent in rows}
            old_map = self._agents
            for name, agent in old_map.items():
                if name not in new_map or new_map[name].switch_agent_id != agent.switch_agent_id:
                    await agent.client.close()
            self._agents = new_map
            log.info("Loaded %s Switch agents", len(self._agents))

    async def close(self) -> None:
        for agent in self._agents.values():
            await agent.client.close()
        self._agents.clear()

    async def post_as(self, chat_name: str, room_id: str, text: str) -> None:
        agent = self._agents.get(chat_name)
        if agent is None:
            # agents provisioned after startup aren't loaded yet, reload once
            await self.refresh()
            agent = self._agents.get(chat_name)
        if agent is None:
            log.warning("Cannot post as unknown agent %s", chat_name)
            return
        await agent.client.post_message(room_id, text)


def set_connection_status(
    switch_agent_id: str, status: SwitchConnectionStatus, connected_at: str = ""
) -> None:
    db = SessionLocal()
    try:
        row = db.execute(
            select(SwitchAgent).where(SwitchAgent.switch_agent_id == switch_agent_id)
        ).scalar_one_or_none()
        if row is None:
            return
        row.connection_status = status
        if connected_at:
            row.last_connected_at = connected_at
        db.commit()
    finally:
        db.close()


registry = AgentRegistry()


__all__ = ["AgentRegistry", "RegisteredAgent", "registry", "set_connection_status"]
