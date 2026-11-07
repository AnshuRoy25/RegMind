from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import websockets

from regmind.app.agents.orchestrator import find_mentioned_agents, handle_message
from regmind.app.agents.runtime import is_agent
from regmind.app.core.config import settings
from regmind.app.core.context import (
    current_agent_id,
    current_org_id,
    current_room_id,
    current_sender,
)
from regmind.app.core.database import SessionLocal
from regmind.app.integrations.switch.agent_registry import (
    RegisteredAgent,
    registry,
    set_connection_status,
)
from regmind.app.models.switch import SwitchConnectionStatus, SwitchEvent
from regmind.app.services.audit_service import audit_service
from regmind.app.services.common import iso, utcnow

log = logging.getLogger("regmind.switch.supervisor")

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _utc_iso() -> str:
    return utcnow().astimezone(timezone.utc).isoformat()


def _safe_filename(name: str, fallback: str = "attachment") -> str:
    cleaned = _SAFE_NAME.sub("_", Path(name or fallback).name)
    return cleaned[:180] or fallback


def _is_recent_processed(message_id: str) -> bool:
    if not message_id:
        return False
    db = SessionLocal()
    try:
        from sqlalchemy import select

        row = db.execute(
            select(SwitchEvent).where(
                SwitchEvent.message_id == message_id,
                SwitchEvent.processed.is_(True),
            )
        ).first()
        return row is not None
    finally:
        db.close()


def record_event(
    *,
    org_id: uuid.UUID | None,
    switch_agent_id: str,
    room_id: str,
    message_id: str,
    event_type: str,
    sender: str,
    payload: dict,
    processed: bool,
) -> None:
    db = SessionLocal()
    try:
        from sqlalchemy import select

        row = db.execute(
            select(SwitchEvent).where(
                SwitchEvent.message_id == message_id,
                SwitchEvent.switch_agent_id == switch_agent_id,
            )
        ).scalar_one_or_none()
        if row is None:
            row = SwitchEvent(
                org_id=org_id,
                switch_agent_id=switch_agent_id,
                room_id=room_id,
                message_id=message_id,
                event_type=event_type,
                sender=sender,
                payload=payload,
                processed=processed,
            )
            db.add(row)
        else:
            row.processed = processed
            row.payload = payload
        db.commit()
    finally:
        db.close()


class SwitchSupervisor:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._cursor = 0
        self._connection_id = ""
        self._started_at = ""
        self._last_error = ""

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def status(self) -> dict[str, object]:
        agent = registry.supervisor_agent()
        return {
            "running": self.running,
            "configured": bool(settings.switch_url),
            "supervisor_agent": agent.chat_name if agent else "",
            "connection_id": self._connection_id,
            "started_at": self._started_at,
            "cursor": self._cursor,
            "last_error": self._last_error,
        }

    async def start(self) -> dict[str, object]:
        if self.running:
            return self.status()
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="regmind-switch-supervisor")
        return self.status()

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        attempt = 0
        while not self._stop.is_set():
            try:
                await registry.refresh()
                agent = registry.supervisor_agent()
                if agent is None:
                    self._last_error = "No Switch agents are provisioned yet"
                    await asyncio.sleep(15)
                    continue
                if not settings.switch_url:
                    self._last_error = "SWITCH_URL is not configured"
                    await asyncio.sleep(30)
                    continue
                self._last_error = ""
                await self._connect(agent)
                attempt = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                attempt += 1
                self._last_error = str(exc)
                log.warning("Switch supervisor error: %s", exc)
                delay = min(30.0, 1.0 * (2 ** min(attempt, 5)))
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass

    async def _connect(self, agent: RegisteredAgent) -> None:
        self._connection_id = str(uuid.uuid4())
        params = {
            "connection_id": self._connection_id,
            "scope": "all",
            "filter": "all",
            "start_from": str(self._cursor) if self._cursor else "head",
            "client": "regmind",
            "client_version": "1.0",
        }
        uri = (
            f"{settings.switch_ws_url}/agents/{agent.switch_agent_id}/connection/ws?"
            f"{urlencode(params)}"
        )
        log.info("Connecting Switch supervisor for %s", agent.chat_name)

        set_connection_status(
            agent.switch_agent_id, SwitchConnectionStatus.CONNECTED, _utc_iso()
        )
        self._started_at = _utc_iso()
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=500)
        try:
            async with websockets.connect(
                uri,
                additional_headers={"Authorization": f"Bearer {agent.api_key}"},
                ping_interval=None,
                close_timeout=5,
                max_size=16 * 1024 * 1024,
            ) as socket:
                worker = asyncio.create_task(
                    self._worker(queue, agent), name="regmind-switch-worker"
                )
                try:
                    async for raw in socket:
                        try:
                            frame = json.loads(raw)
                        except (ValueError, TypeError):
                            continue
                        event = frame.get("event")
                        if frame.get("id") is not None:
                            self._cursor = int(frame["id"])
                        if event == "ping":
                            await socket.send(
                                json.dumps({"type": "pong", "cursor": self._cursor})
                            )
                        elif event == "connection_state":
                            log.info(
                                "Switch connection ready: %s",
                                (frame.get("data") or {}).get("connection_id"),
                            )
                        elif event == "refused":
                            detail = (frame.get("data") or {}).get("detail")
                            raise RuntimeError(f"Switch refused the connection: {detail}")
                        elif event == "evicted":
                            detail = (frame.get("data") or {}).get("code")
                            log.warning("Switch connection evicted: %s", detail)
                            return
                        elif event == "message":
                            data = frame.get("data") or {}
                            try:
                                queue.put_nowait(data)
                            except asyncio.QueueFull:
                                log.error(
                                    "Switch message queue full; dropping event %s",
                                    (data.get("payload") or {}).get("message_id"),
                                )
                finally:
                    worker.cancel()
                    try:
                        await worker
                    except (asyncio.CancelledError, Exception):
                        pass
        finally:
            set_connection_status(agent.switch_agent_id, SwitchConnectionStatus.DISCONNECTED)

    async def _worker(self, queue: asyncio.Queue[dict], agent: RegisteredAgent) -> None:
        while True:
            data = await queue.get()
            try:
                await self._handle_message(data, agent)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Failed to handle Switch message")
            finally:
                queue.task_done()

    async def _handle_message(self, data: dict, agent: RegisteredAgent) -> None:
        payload = data.get("payload") or {}
        if not isinstance(payload, dict):
            return

        sender_kind = payload.get("sender_kind")
        sender = str(payload.get("sender") or "")
        sender_name = str(payload.get("sender_name") or sender)
        if sender_kind == "agent":
            return
        if sender_kind is None and is_agent(sender_name):
            return

        room_id = str(data.get("room_id") or "")
        message_id = str(payload.get("message_id") or "")
        if not room_id or not message_id:
            return
        if message_id in self._seen_messages():
            return
        if _is_recent_processed(message_id):
            self._remember_message(message_id)
            return

        log.info("Switch payload: %s", payload)
        body = str(payload.get("body") or "").strip()
        attachments = payload.get("attachments") or []
        file_paths: list[str] = []
        for attachment in attachments:
            path = await self._download_attachment(room_id, attachment, agent)
            if path:
                file_paths.append(path)

        text = body
        if file_paths:
            if not text:
                text = "Please review the attached SEBI circular."
            text += "\n\nAttached file(s):\n" + "\n".join(file_paths)

        mentions = find_mentioned_agents(text, sender_name)
        if not mentions:
            # Discord mentions can arrive without the "@regmind-x" text,
            # so anything reaching intake's socket goes to intake by default
            text = "@regmind-intake " + text
            mentions = ["regmind-intake"]

        self._remember_message(message_id)
        record_event(
            org_id=agent.org_id,
            switch_agent_id=agent.switch_agent_id,
            room_id=room_id,
            message_id=message_id,
            event_type="message",
            sender=sender,
            payload=payload,
            processed=False,
        )

        org_token = current_org_id.set(agent.org_id)
        room_token = current_room_id.set(room_id)
        sender_token = current_sender.set(sender_name)
        agent_token = current_agent_id.set(agent.chat_name)
        try:
            await handle_message(room_id, sender_name, text, self._post)
            record_event(
                org_id=agent.org_id,
                switch_agent_id=agent.switch_agent_id,
                room_id=room_id,
                message_id=message_id,
                event_type="message",
                sender=sender,
                payload=payload,
                processed=True,
            )
        finally:
            current_agent_id.reset(agent_token)
            current_sender.reset(sender_token)
            current_room_id.reset(room_token)
            current_org_id.reset(org_token)

    async def _post(self, agent_name: str, room_id: str, text: str) -> None:
        if not text.strip():
            return
        try:
            await registry.post_as(agent_name, room_id, text)
        except Exception:
            log.exception("Could not post as %s in room %s", agent_name, room_id)
            await audit_service.log(
                actor="regmind-switch",
                action="agent_post_failed",
                ref_id=room_id,
                detail={"agent": agent_name, "room_id": room_id},
            )

    async def _download_attachment(
        self, room_id: str, attachment: dict, agent: RegisteredAgent
    ) -> str:
        log.info("Attachment received: %s", attachment)
        mxc = str(attachment.get("mxc") or "")
        url = str(attachment.get("url") or attachment.get("download_url") or "")
        if not mxc and not url:
            log.warning("Attachment has no mxc or url, skipping")
            return ""
        filename = _safe_filename(str(attachment.get("filename") or attachment.get("name") or "attachment"))
        size = int(attachment.get("size") or 0)
        if size and size > settings.max_upload_mb * 1024 * 1024:
            log.warning("Skipping oversized attachment %s (%s bytes)", filename, size)
            return ""
        try:
            if mxc:
                data = await agent.client.download_media(room_id, mxc)
            else:
                import httpx
                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.content
        except Exception as exc:
            log.warning("Could not download attachment %s: %s", filename, exc)
            return ""
        directory = settings.storage_dir / "switch" / "attachments" / _safe_filename(room_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{uuid.uuid4().hex[:12]}-{filename}"
        await asyncio.to_thread(path.write_bytes, data)
        log.info("Saved attachment to %s", path)
        return str(path.resolve())

    _memory_seen: set[str] = set()

    def _seen_messages(self) -> set[str]:
        return self._memory_seen

    def _remember_message(self, message_id: str) -> None:
        self._memory_seen.add(message_id)
        if len(self._memory_seen) > 5000:
            self._memory_seen = set(list(self._memory_seen)[-2000:])


supervisor = SwitchSupervisor()


__all__ = ["SwitchSupervisor", "supervisor"]
