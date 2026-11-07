from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from regmind.app.core.config import settings

log = logging.getLogger("regmind.switch.gateway")


class SwitchError(RuntimeError):
    pass


class SwitchNotConfigured(SwitchError):
    pass


class SwitchAPIError(SwitchError):
    def __init__(self, method: str, path: str, status_code: int, detail: Any) -> None:
        self.method = method
        self.path = path
        self.status_code = status_code
        self.detail = detail
        if isinstance(detail, dict):
            detail_text = detail.get("detail") or detail.get("message") or detail
        else:
            detail_text = detail
        super().__init__(f"{method} {path} -> {status_code}: {detail_text}")


def _tenant_matches(tenant: dict[str, Any], wanted_id: str, wanted_name: str) -> bool:
    if wanted_id and tenant.get("id") == wanted_id:
        return True
    if wanted_name and str(tenant.get("name", "")).strip().lower() == wanted_name.strip().lower():
        return True
    return False


class SwitchGateway:
    def __init__(self) -> None:
        self._http: httpx.AsyncClient | None = None
        self._login_lock = asyncio.Lock()
        self._logged_in = False
        self._user: dict[str, Any] = {}

    @property
    def configured(self) -> bool:
        return bool(settings.switch_url and settings.switch_email and settings.switch_password)

    def _require_configured(self) -> None:
        if not self.configured:
            raise SwitchNotConfigured(
                "Switch is not configured. Set SWITCH_URL, SWITCH_EMAIL and SWITCH_PASSWORD."
            )

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=settings.switch_api_url,
                timeout=settings.switch_request_timeout,
                verify=settings.switch_verify_tls,
                follow_redirects=True,
                headers={"Accept": "application/json", "User-Agent": "regmind/1.0"},
            )
        return self._http

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None
        self._logged_in = False

    async def login(self) -> dict[str, Any]:
        self._require_configured()
        async with self._login_lock:
            response = await self._client().post(
                "/gateway/auth/login",
                json={"email": settings.switch_email, "password": settings.switch_password},
            )
            if response.status_code >= 400:
                raise SwitchAPIError("POST", "/gateway/auth/login", response.status_code, self._detail(response))
            self._logged_in = True
            self._user = response.json()
            return self._user

    async def _ensure_login(self) -> None:
        if not self._logged_in:
            await self.login()

    @staticmethod
    def _detail(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return response.text[:500]

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        self._require_configured()
        await self._ensure_login()
        response = await self._client().request(method, path, **kwargs)
        if response.status_code == 401:
            await self.login()
            response = await self._client().request(method, path, **kwargs)
        if response.status_code >= 400:
            raise SwitchAPIError(method, path, response.status_code, self._detail(response))
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    async def session_state(self) -> dict[str, Any]:
        return await self._request("GET", "/gateway/auth/session")

    async def create_organization(self, name: str, workspace_name: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/gateway/organizations",
            json={"name": name, "workspace_name": workspace_name},
        )

    async def list_workspaces(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/gateway/organizations/current/workspaces")

    async def create_workspace(self, name: str) -> dict[str, Any]:
        return await self._request(
            "POST", "/gateway/organizations/current/workspaces", json={"name": name}
        )

    async def switch_tenant(self, tenant_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/gateway/tenants/{tenant_id}/switch")

    async def create_registration_key(self, label: str = "regmind-agents") -> str:
        data = await self._request(
            "POST",
            "/gateway/api-keys",
            json={"label": label, "expires_in_days": "never"},
        )
        key = data.get("key") if isinstance(data, dict) else None
        if not key:
            raise SwitchError("Switch did not return an API key")
        return str(key)

    async def create_room(
        self,
        *,
        name: str,
        description: str,
        instructions: str = "",
        agent_ids: list[str] | None = None,
        internal_only: bool = False,
        channel_type: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "description": description,
            "instructions": instructions or None,
            "agent_ids": agent_ids or [],
            "internal_only": internal_only,
        }
        if channel_type:
            payload["channel_type"] = channel_type
        return await self._request("POST", "/gateway/rooms", json=payload)

    async def add_room_agents(self, room_id: str, agent_ids: list[str]) -> Any:
        return await self._request(
            "POST", f"/gateway/rooms/{room_id}/agents", json={"agent_ids": agent_ids}
        )

    async def set_addressing_open(self, agent_id: str) -> Any:
        return await self._request(
            "PUT",
            f"/gateway/agents/{agent_id}/addressing-policy",
            json={"policy": None},
        )

    async def list_agents(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/gateway/agents")

    async def begin_messaging_install(self, platform: str = "discord") -> dict[str, Any]:
        return await self._request(
            "POST", f"/gateway/messaging-apps/{platform}/install"
        )

    def authorize_url(self, data: dict[str, Any] | None) -> str:
        if not data:
            return ""
        return str(data.get("authorize_url") or data.get("url") or "")

    async def ensure_workspace(
        self,
        *,
        organization_name: str,
        workspace_name: str,
        preferred_tenant_id: str = "",
    ) -> dict[str, Any]:
        await self.login()
        state = await self.session_state()
        status = state.get("state")
        tenant = state.get("tenant")
        tenants = state.get("tenants") or []
        wanted_id = preferred_tenant_id or settings.switch_tenant_id
        wanted_name = workspace_name or settings.switch_workspace_name

        if status == "needs_workspace":
            if not state.get("can_create_workspace"):
                raise SwitchError(
                    "The Switch account has no workspace and is not allowed to create one."
                )
            created = await self.create_organization(organization_name, wanted_name)
            workspace = created.get("workspace") or {}
            organization = created.get("organization") or {}
            return {"workspace": workspace, "organization": organization, "created": True}

        if status == "needs_selection":
            chosen = self._pick_tenant(tenants, wanted_id, wanted_name)
            if chosen is None:
                raise SwitchError(
                    f"No Switch workspace matches '{wanted_name}'. Set SWITCH_TENANT_ID."
                )
            await self.switch_tenant(str(chosen["id"]))
            return {"workspace": chosen, "organization": {}, "created": False}

        if not isinstance(tenant, dict):
            raise SwitchError("Switch session has no workspace selected.")

        if wanted_id and tenant.get("id") != wanted_id:
            matching = next((t for t in tenants if t.get("id") == wanted_id), None)
            if matching is None:
                raise SwitchError(
                    f"SWITCH_TENANT_ID={wanted_id} is not one of this account's workspaces."
                )
            await self.switch_tenant(wanted_id)
            tenant = matching
        elif not wanted_id and not _tenant_matches(tenant, "", wanted_name):
            matching = self._pick_tenant(tenants, "", wanted_name)
            if matching is not None and matching.get("id") != tenant.get("id"):
                await self.switch_tenant(str(matching["id"]))
                tenant = matching

        return {"workspace": tenant, "organization": {}, "created": False}

    @staticmethod
    def _pick_tenant(
        tenants: list[dict[str, Any]], wanted_id: str, wanted_name: str
    ) -> dict[str, Any] | None:
        if wanted_id:
            for tenant in tenants:
                if tenant.get("id") == wanted_id:
                    return tenant
        if wanted_name:
            for tenant in tenants:
                if _tenant_matches(tenant, "", wanted_name):
                    return tenant
        return tenants[0] if tenants else None


_gateway: SwitchGateway | None = None


def get_gateway() -> SwitchGateway:
    global _gateway
    if _gateway is None:
        _gateway = SwitchGateway()
    return _gateway


async def close_gateway() -> None:
    global _gateway
    if _gateway is not None:
        await _gateway.close()
        _gateway = None


__all__ = [
    "SwitchAPIError",
    "SwitchError",
    "SwitchGateway",
    "SwitchNotConfigured",
    "close_gateway",
    "get_gateway",
]
