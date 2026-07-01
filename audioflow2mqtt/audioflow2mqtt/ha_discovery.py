"""Pure builders for Home Assistant MQTT discovery payloads.

Produces the retained `homeassistant/.../config` messages that make entities
appear automatically in Home Assistant. Payloads are serialized to JSON here and
returned as PublishMessage, so every discovery publish crosses the transport
seam as the same type as any other publish. No I/O.
"""
from __future__ import annotations

import json

from .device import DeviceInfo, Zone
from .mqtt import PublishMessage


def build_device_discovery(base_topic: str, info: DeviceInfo, zones: list[Zone]) -> list[PublishMessage]:
    common = {
        "availability": [
            {"topic": f"{base_topic}/status"},
            {"topic": f"{base_topic}/{info.serial}/status"},
        ],
        "device": {
            "name": info.name,
            "identifiers": info.serial,
            "manufacturer": "Audioflow",
            "model": info.model,
            "sw_version": info.fw_version,
        },
        "platform": "mqtt",
    }
    messages: list[PublishMessage] = []
    for zone in zones:
        x = zone.number
        suffix = "" if zone.enabled else " (Disabled)"
        messages.append(_config(
            f"homeassistant/switch/{info.serial}/{x}/config",
            {
                **common,
                "name": f"{zone.name} speakers{suffix}",
                "command_topic": f"{base_topic}/{info.serial}/set_zone_state/{x}",
                "state_topic": f"{base_topic}/{info.serial}/zone_state/{x}",
                "payload_on": "on",
                "payload_off": "off",
                "unique_id": f"{info.serial}{x}",
            },
        ))

    for state in ("off", "on"):
        messages.append(_config(
            f"homeassistant/button/{info.serial}/all_zones_{state}/config",
            {
                **common,
                "name": f"Turn all zones {state}",
                "command_topic": f"{base_topic}/{info.serial}/set_zone_state",
                "payload_press": state,
                "unique_id": f"{info.serial}_all_zones_{state}",
                "icon": f"mdi:power-{state}",
            },
        ))

    messages.append(_config(
        f"homeassistant/button/{info.serial}/reboot/config",
        {
            **common,
            "name": "Reboot",
            "command_topic": f"{base_topic}/{info.serial}/reboot",
            "payload_press": "reboot",
            "unique_id": f"{info.serial}_reboot",
            "icon": "mdi:restart",
        },
    ))

    for key, name, icon in _SENSORS:
        messages.append(_config(
            f"homeassistant/sensor/{info.serial}/{key}/config",
            {
                **common,
                "name": name,
                "state_topic": f"{base_topic}/{info.serial}/network_info/{key}",
                "icon": icon,
                "unique_id": f"{info.serial}{key}",
            },
        ))
    return messages


def _config(topic: str, payload: dict) -> PublishMessage:
    """A retained discovery config message with a JSON-serialized payload."""
    return PublishMessage(topic=topic, payload=json.dumps(payload), qos=1, retain=True)


_SENSORS = (
    ("ssid", "SSID", "mdi:access-point-network"),
    ("channel", "Wi-Fi channel", "mdi:access-point"),
    ("rssi", "RSSI", "mdi:signal"),
)
