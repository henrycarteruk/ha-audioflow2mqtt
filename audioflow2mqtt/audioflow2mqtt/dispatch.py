"""Pure planning of inbound commands into concrete device actions.

`plan_action` takes a parsed command plus the device's current zones and
returns a typed Action (or None if the command can't be applied). All the
stateful glue — toggle resolution, zone existence/enabled checks — lives here
as pure logic; the orchestrator just executes the returned Action.
"""
from __future__ import annotations

from dataclasses import dataclass

from .commands import SetZoneState, SetAllZones, SetZoneEnable, Reboot, Discover
from .device import Zone


@dataclass(frozen=True)
class ApplyZoneState:
    serial: str
    zone: int
    on: bool


@dataclass(frozen=True)
class ApplyAllZones:
    serial: str
    on: bool
    zone_count: int


@dataclass(frozen=True)
class ApplyZoneEnable:
    serial: str
    zone: int
    enabled: bool
    name: str


def plan_action(command, zones: list[Zone] | None):
    if isinstance(command, Discover):
        return command
    if isinstance(command, Reboot):
        return command if zones is not None else None
    if isinstance(command, SetZoneState):
        zone = _find(zones, command.zone)
        if zone is None or not zone.enabled:
            return None
        if command.value == "toggle":
            on = zone.state != "on"
        else:
            on = command.value == "on"
        return ApplyZoneState(serial=command.serial, zone=command.zone, on=on)
    if isinstance(command, SetAllZones):
        return ApplyAllZones(
            serial=command.serial, on=command.value == "on", zone_count=len(zones or [])
        )
    if isinstance(command, SetZoneEnable):
        zone = _find(zones, command.zone)
        if zone is None:
            return None
        return ApplyZoneEnable(
            serial=command.serial,
            zone=command.zone,
            enabled=bool(command.enabled),
            name=zone.name,
        )
    return None


def _find(zones: list[Zone] | None, number: int) -> Zone | None:
    for zone in zones or []:
        if zone.number == number:
            return zone
    return None
