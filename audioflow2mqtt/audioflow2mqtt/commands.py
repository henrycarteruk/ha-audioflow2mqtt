"""Pure parsing of incoming MQTT command topics into typed commands.

Parsing is deliberately separated from execution: this module never performs
I/O. The async layer consumes the returned command objects.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SetZoneState:
    serial: str
    zone: int
    value: str


@dataclass(frozen=True)
class SetAllZones:
    serial: str
    value: str


@dataclass(frozen=True)
class SetZoneEnable:
    serial: str
    zone: int
    enabled: int


@dataclass(frozen=True)
class Reboot:
    serial: str


@dataclass(frozen=True)
class Discover:
    pass


def parse_command(base_topic: str, topic: str, payload: str):
    parts = topic.split("/")
    if len(parts) < 2 or parts[0] != base_topic:
        return None
    # Gateway-scoped: base_topic / discover
    if parts[1] == "discover":
        return Discover()
    # Device-scoped: base_topic / serial / command [ / zone ]
    if len(parts) < 3:
        return None
    serial = parts[1]
    if parts[2] == "set_zone_state":
        if len(parts) > 3:
            zone = _to_int(parts[3])
            if zone is None or payload not in ("on", "off", "toggle"):
                return None
            return SetZoneState(serial=serial, zone=zone, value=payload)
        if payload not in ("on", "off"):
            return None
        return SetAllZones(serial=serial, value=payload)
    if parts[2] == "set_zone_enable" and len(parts) > 3:
        zone = _to_int(parts[3])
        enabled = _to_int(payload)
        if zone is None or enabled not in (0, 1):
            return None
        return SetZoneEnable(serial=serial, zone=zone, enabled=enabled)
    if parts[2] == "reboot":
        return Reboot(serial=serial)
    return None


def _to_int(value: str):
    try:
        return int(value)
    except ValueError:
        return None
