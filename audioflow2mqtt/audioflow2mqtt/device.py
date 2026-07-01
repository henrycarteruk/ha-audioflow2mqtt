"""Async HTTP client for a single Audioflow device.

Wraps the device's HTTP API (/switch, /zones, /zonename/{n}) behind a small
typed interface. The httpx.AsyncClient is injected so connections are pooled
and the client is testable. Non-2xx responses raise (raise_for_status); the
orchestration layer decides how to react.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class DeviceInfo:
    serial: str
    model: str
    name: str
    fw_version: str
    wifi: str


@dataclass(frozen=True)
class Zone:
    number: int
    name: str
    state: str
    enabled: bool


class AudioflowClient:
    def __init__(self, ip: str, http: httpx.AsyncClient):
        self._base = f"http://{ip}/"
        self._http = http

    async def _get(self, path: str) -> dict:
        resp = await self._http.get(self._base + path)
        resp.raise_for_status()
        return resp.json()

    async def _put(self, path: str, body: str) -> None:
        resp = await self._http.put(self._base + path, content=body)
        resp.raise_for_status()

    async def get_info(self) -> DeviceInfo:
        data = await self._get("switch")
        return DeviceInfo(
            serial=data["serial"],
            model=data["model"],
            name=data["name"],
            fw_version=data["version"],
            wifi=data["wifi"],
        )

    async def get_zones(self) -> list[Zone]:
        zones = (await self._get("zones"))["zones"]
        return [
            Zone(
                number=i,
                name=z["name"],
                state=z["state"],
                enabled=bool(z["enabled"]),
            )
            for i, z in enumerate(zones, start=1)
        ]

    async def set_zone_state(self, zone: int, on: bool) -> None:
        await self._put(f"zones/{zone}", "1" if on else "0")

    async def set_all_zones(self, on: bool, zone_count: int) -> None:
        await self._put("zones", " ".join(["1" if on else "0"] * zone_count))

    async def set_zone_enable(self, zone: int, enabled: bool, name: str) -> None:
        # The device requires the existing zone name echoed back in the payload.
        await self._put(f"zonename/{zone}", f"{1 if enabled else 0}{name}")

    async def reboot(self) -> None:
        # Response body is not JSON; raise_for_status is enough.
        resp = await self._http.get(self._base + "reboot_now")
        resp.raise_for_status()
