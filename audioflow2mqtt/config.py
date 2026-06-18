"""Pure resolution of add-on configuration into a typed Config.

Merges the parsed /data/options.json with the (optional) Supervisor MQTT
service data. This module performs no I/O: fetching the options file and the
Supervisor service is done elsewhere and passed in.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class Config:
    mqtt_host: str | None
    mqtt_port: int
    mqtt_user: str | None
    mqtt_pass: str | None
    qos: int
    base_topic: str
    devices: list[str] | None
    log_level: str
    home_assistant: bool = True


def load_options(path: str = "/data/options.json") -> dict:
    """Read the add-on options file written by the Supervisor."""
    with open(path) as file:
        return json.load(file)


async def fetch_mqtt_service(http: httpx.AsyncClient, token: str | None) -> dict | None:
    """Fetch MQTT broker config from the Supervisor services API, or None."""
    if not token:
        return None
    try:
        resp = await http.get(
            "http://supervisor/services/mqtt",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
    except httpx.HTTPError:
        return None
    return resp.json().get("data")


def _pick(*candidates):
    """Return the first explicitly-set value (non-None, non-empty-string)."""
    for value in candidates:
        if value is not None and value != "":
            return value
    return None


def resolve_config(options: dict, mqtt_service: dict | None = None) -> Config:
    service = mqtt_service or {}
    return Config(
        mqtt_host=_pick(options.get("mqtt_host"), service.get("host")),
        mqtt_port=_pick(options.get("mqtt_port"), service.get("port"), 1883),
        mqtt_user=_pick(options.get("mqtt_user"), service.get("username")),
        mqtt_pass=_pick(options.get("mqtt_pass"), service.get("password")),
        qos=options.get("qos") if options.get("qos") is not None else 1,
        base_topic=options.get("base_topic") or "audioflow2mqtt",
        devices=_clean_devices(options.get("devices")),
        log_level=_clean_log_level(options.get("log_level")),
    )


_VALID_LOG_LEVELS = ("debug", "info", "warning", "error")


def _clean_log_level(level) -> str:
    normalized = str(level or "").lower()
    return normalized if normalized in _VALID_LOG_LEVELS else "info"


def _clean_devices(devices) -> list[str] | None:
    if not devices:
        return None
    cleaned = [d for d in devices if d not in (None, "")]
    return cleaned or None
