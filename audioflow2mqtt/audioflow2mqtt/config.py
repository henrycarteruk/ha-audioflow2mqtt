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


def resolve_config(options: dict, mqtt_service: dict | None = None) -> Config:
    service = mqtt_service or {}
    pick = lambda *c: next((v for v in c if v is not None and v != ""), None)
    return Config(
        mqtt_host=pick(options.get("mqtt_host"), service.get("host")),
        mqtt_port=pick(options.get("mqtt_port"), service.get("port"), 1883),
        mqtt_user=pick(options.get("mqtt_user"), service.get("username")),
        mqtt_pass=pick(options.get("mqtt_pass"), service.get("password")),
        qos=options.get("qos") if options.get("qos") is not None else 1,
        base_topic=options.get("base_topic") or "audioflow2mqtt",
        devices=[d for d in (options.get("devices") or []) if d not in (None, "")] or None,
        log_level=_lv if (_lv := str(options.get("log_level") or "").lower()) in ("debug", "info", "warning", "error") else "info",
    )
