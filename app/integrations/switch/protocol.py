from __future__ import annotations

import logging
from typing import Any

import httpx

from regmind.app.core.config import settings

log = logging.getLogger("regmind.switch.protocol")


class SwitchProtocolError(RuntimeError):
    pass


def _base_url() -> str:
    if not settings.switch_url:
        raise SwitchProtocolError("SWITCH_URL is not configured")
    return settings.switch_api_url


def _client(api_key: str | None = None) -> httpx.AsyncClient:
    headers = {"Accept": "application/json", "User-Agent": "regmind/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return httpx.AsyncClient(
        base_url=_base_url(),
        timeout=settings.switch_request_timeout,
        verify=settings.switch_verify_tls,
        headers=headers,
    )


def _detail(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:500]


async def register_agent(
    *,
    registration_key: str,
    name: str,
    description: str,
    display_name: str = "",
    connector_type: str = "regmind",
    tools: list[dict[str, Any]] | None = None,
    models: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    payload = {
        "name": name,
        "description": description,
        "display_name": display_name or None,
        "connector_type": connector_type,
        "integration_profile": {
            "connection_model": "always_on",
            "message_exchange": True,
            "pre_invocation_mediation": [],
            "post_invocation_mediation": [],
            "event_reporting": [],
        },
        "tools": tools or [],
        "models": models or [],
        "metadata": metadata or {},
        "overwrite": overwrite,
    }
    async with _client(registration_key) as client:
        response = await client.post("/agents", json=payload)
    if response.status_code >= 400:
        raise SwitchProtocolError(
            f"Agent registration failed ({response.status_code}): {_detail(response)}"
        )
    data = response.json()
    if not data.get("id") or not data.get("api_key"):
        raise SwitchProtocolError("Agent registration returned no id or api_key")
    return data


class SwitchProtocolClient:
    def __init__(self, agent_id: str, api_key: str) -> None:
        self.agent_id = agent_id
        self.api_key = api_key
        self._http: httpx.AsyncClient | None = None

    def _get(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = _client(self.api_key)
            self._http.headers["X-Agent-Id"] = self.agent_id
        return self._http

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    def _check(self, response: httpx.Response, action: str) -> Any:
        if response.status_code >= 400:
            raise SwitchProtocolError(
                f"{action} failed ({response.status_code}): {_detail(response)}"
            )
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    async def post_message(self, room_id: str, content: str) -> Any:
        response = await self._get().post(
            f"/agents/{self.agent_id}/message",
            json={"room_id": room_id, "content": content},
        )
        return self._check(response, "post_message")

    async def set_typing(self, room_id: str, is_typing: bool) -> Any:
        response = await self._get().post(
            f"/agents/{self.agent_id}/typing",
            json={"room_id": room_id, "is_typing": is_typing},
        )
        return self._check(response, "set_typing")

    async def download_media(self, room_id: str, mxc: str) -> bytes:
        response = await self._get().get(
            f"/agents/{self.agent_id}/rooms/{room_id}/media",
            params={"mxc": mxc},
        )
        if response.status_code >= 400:
            raise SwitchProtocolError(
                f"download_media failed ({response.status_code}): {_detail(response)}"
            )
        return response.content

    async def upload_media(
        self,
        room_id: str,
        files: list[tuple[bytes, str, str]],
        *,
        caption: str | None = None,
        thread_id: str | None = None,
    ) -> Any:
        form: dict[str, Any] = {}
        if caption:
            form["caption"] = caption
        if thread_id:
            form["thread_id"] = thread_id
        multipart = [
            ("files", (filename, data, mimetype))
            for data, filename, mimetype in files
        ]
        response = await self._get().post(
            f"/agents/{self.agent_id}/rooms/{room_id}/media",
            data=form,
            files=multipart,
        )
        return self._check(response, "upload_media")

    async def update_agent_detail(self, **fields: Any) -> Any:
        response = await self._get().post(
            f"/agents/{self.agent_id}/ops/update_agent_detail",
            json={k: v for k, v in fields.items() if v is not None},
        )
        return self._check(response, "update_agent_detail")

    async def __aenter__(self) -> "SwitchProtocolClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()


__all__ = ["SwitchProtocolClient", "SwitchProtocolError", "register_agent"]
