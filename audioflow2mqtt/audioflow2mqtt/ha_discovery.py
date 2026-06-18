"""Pure builders for Home Assistant MQTT discovery payloads.

Produces the retained `homeassistant/.../config` messages that make entities
appear automatically in Home Assistant. No I/O: the async MQTT layer serializes
each payload and publishes it.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoveryMessage:
    topic: str
    payload: dict


@dataclass(frozen=True)
class DiscoveryZone:
    number: int
    name: str
    enabled: bool


@dataclass(frozen=True)
class DiscoveryDevice:
    serial: str
    name: str
    model: str
    fw_version: str
    zones: list[DiscoveryZone]


def build_device_discovery(base_topic: str, device: DiscoveryDevice) -> list[DiscoveryMessage]:
    common = {
        "availability": [
            {"topic": f"{base_topic}/status"},
            {"topic": f"{base_topic}/{device.serial}/status"},
        ],
        "device": {
            "name": device.name,
            "identifiers": device.serial,
            "manufacturer": "Audioflow",
            "model": device.model,
            "sw_version": device.fw_version,
        },
        "platform": "mqtt",
    }
    messages: list[DiscoveryMessage] = []
    for zone in device.zones:
        x = zone.number
        suffix = "" if zone.enabled else " (Disabled)"
        messages.append(DiscoveryMessage(
            topic=f"homeassistant/switch/{device.serial}/{x}/config",
            payload={
                **common,
                "name": f"{zone.name} speakers{suffix}",
                "command_topic": f"{base_topic}/{device.serial}/set_zone_state/{x}",
                "state_topic": f"{base_topic}/{device.serial}/zone_state/{x}",
                "payload_on": "on",
                "payload_off": "off",
                "unique_id": f"{device.serial}{x}",
            },
        ))

    for state in ("off", "on"):
        messages.append(DiscoveryMessage(
            topic=f"homeassistant/button/{device.serial}/all_zones_{state}/config",
            payload={
                **common,
                "name": f"Turn all zones {state}",
                "command_topic": f"{base_topic}/{device.serial}/set_zone_state",
                "payload_press": state,
                "unique_id": f"{device.serial}_all_zones_{state}",
                "icon": f"mdi:power-{state}",
            },
        ))

    for key, name, icon in _SENSORS:
        messages.append(DiscoveryMessage(
            topic=f"homeassistant/sensor/{device.serial}/{key}/config",
            payload={
                **common,
                "name": name,
                "state_topic": f"{base_topic}/{device.serial}/network_info/{key}",
                "icon": icon,
                "unique_id": f"{device.serial}{key}",
            },
        ))
    return messages


_SENSORS = (
    ("ssid", "SSID", "mdi:access-point-network"),
    ("channel", "Wi-Fi channel", "mdi:access-point"),
    ("rssi", "RSSI", "mdi:signal"),
)
