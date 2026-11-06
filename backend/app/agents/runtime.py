"""
Runs one agent on one message and returns its reply.

    reply = await runtime.run("regmind-parser", room_id="regmind", text="[priya] ...")

- One ADK Runner per agent, created once at import.
- One session per (room, agent), so each agent remembers its own thread in each room.
- A lock per session, so two messages for the same agent in the same room are
  processed one after the other instead of corrupting the session.
"""

import asyncio
import logging

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from regmind.backend.app.agents.definitions import AGENTS
from regmind.backend.app.core.config import settings

log = logging.getLogger("regmind.agents")

APP_NAME = "regmind"


def _make_session_service():
    if settings.adk_sessions_db_url:
        from google.adk.sessions import DatabaseSessionService
        return DatabaseSessionService(db_url=settings.adk_sessions_db_url)
    return InMemorySessionService()


session_service = _make_session_service()

runners: dict[str, Runner] = {}
for chat_name, adk_agent in AGENTS.items():
    runners[chat_name] = Runner(agent=adk_agent, app_name=APP_NAME, session_service=session_service)

_locks: dict[str, asyncio.Lock] = {}


def is_agent(name: str) -> bool:
    return name in AGENTS


async def _ensure_session(room_id: str, session_id: str) -> None:
    existing = await session_service.get_session(app_name=APP_NAME, user_id=room_id, session_id=session_id)
    if existing is None:
        await session_service.create_session(app_name=APP_NAME, user_id=room_id, session_id=session_id)


async def run(agent_name: str, room_id: str, text: str) -> str:
    """Send `text` to `agent_name` in `room_id` and return its final reply ("" if none)."""
    if agent_name not in runners:
        raise ValueError(f"Unknown agent {agent_name}")

    session_id = f"{room_id}:{agent_name}"
    lock = _locks.setdefault(session_id, asyncio.Lock())

    async with lock:
        await _ensure_session(room_id, session_id)
        message = types.Content(role="user", parts=[types.Part(text=text)])
        reply_parts: list[str] = []
        try:
            async for event in runners[agent_name].run_async(
                user_id=room_id, session_id=session_id, new_message=message
            ):
                for call in event.get_function_calls():
                    log.info("%s -> %s(%s)", agent_name, call.name, dict(call.args or {}))
                if event.is_final_response() and event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            reply_parts.append(part.text)
        except Exception:
            log.exception("Agent %s failed in room %s", agent_name, room_id)
            return f"⚠️ {agent_name} hit an internal error and could not finish. Please try again."

    return "\n".join(reply_parts).strip()
