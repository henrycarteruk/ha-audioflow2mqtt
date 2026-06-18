"""Orchestrator: wires config, device clients and the MQTT transport together.

Dependencies are injected so the orchestration logic is testable without a real
broker or device. The thin __main__ entrypoint builds the real dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from .commands import parse_command
from .config import Config
from .device import AudioflowClient, DeviceInfo, Zone
from .dispatch import (
    plan_action,
    ApplyZoneState,
    ApplyAllZones,
    ApplyZoneEnable,
    TriggerDiscovery,
)
from .ha_discovery import build_device_discovery, DiscoveryDevice, DiscoveryZone
from .health import DeviceHealth
from .mqtt import (
    zone_messages,
    network_messages,
    device_status_message,
    gateway_status_message,
    subscribe_topics,
)
from .wifi import parse_wifi


@dataclass
class Device:
    client: AudioflowClient
    info: DeviceInfo
    zones: list[Zone]
    health: DeviceHealth = field(default_factory=DeviceHealth)


def _discovery_device(device: "Device") -> DiscoveryDevice:
    return DiscoveryDevice(
        serial=device.info.serial,
        name=device.info.name,
        model=device.info.model,
        fw_version=device.info.fw_version,
        zones=[DiscoveryZone(number=z.number, name=z.name, enabled=z.enabled) for z in device.zones],
    )


class Orchestrator:
    def __init__(self, config: Config, transport, devices: dict[str, Device], *, http=None, discover=None):
        self._config = config
        self._transport = transport
        self._devices = devices
        self._http = http
        self._discover = discover

    async def on_connect(self) -> None:
        """Re-publish subscriptions, discovery and status after each (re)connect."""
        await self._transport.subscribe(subscribe_topics(self._config.base_topic, list(self._devices)))
        await self._transport.publish(gateway_status_message(self._config.base_topic, True))
        for serial, device in self._devices.items():
            await self._announce_device(serial, device)

    async def _announce_device(self, serial: str, device: Device) -> None:
        for message in build_device_discovery(self._config.base_topic, _discovery_device(device)):
            await self._transport.publish(message)
        await self._transport.publish(device_status_message(self._config.base_topic, serial, True))

    async def rediscover(self) -> None:
        for ip in await self._discover():
            device = await self._acquire(ip)
            serial = device.info.serial
            if serial in self._devices:
                continue
            self._devices[serial] = device
            await self._transport.subscribe([f"{self._config.base_topic}/{serial}/#"])
            await self._announce_device(serial, device)

    async def _acquire(self, ip: str) -> Device:
        client = AudioflowClient(ip, self._http)
        info = await client.get_info()
        zones = await client.get_zones()
        return Device(client=client, info=info, zones=zones)

    async def handle_message(self, topic: str, payload: str) -> None:
        command = parse_command(self._config.base_topic, topic, payload)
        if command is None:
            return
        action = plan_action(command, self._zones_for(command))
        if action is None:
            return
        if isinstance(action, TriggerDiscovery):
            await self.rediscover()
            return
        await self.execute(action)
        await self.refresh_state(action.serial)

    def _zones_for(self, command):
        serial = getattr(command, "serial", None)
        device = self._devices.get(serial) if serial else None
        return device.zones if device else None

    async def execute(self, action) -> None:
        device = self._devices[action.serial]
        if isinstance(action, ApplyZoneState):
            await device.client.set_zone_state(action.zone, action.on)
        elif isinstance(action, ApplyAllZones):
            await device.client.set_all_zones(action.on, action.zone_count)
        elif isinstance(action, ApplyZoneEnable):
            await device.client.set_zone_enable(action.zone, action.enabled, action.name)

    async def refresh_state(self, serial: str) -> None:
        device = self._devices[serial]
        was_online = device.health.online
        try:
            device.zones = await device.client.get_zones()
        except httpx.HTTPError:
            device.health = device.health.failed()
            await self._publish_transition(serial, was_online, device.health.online)
            return
        device.health = device.health.succeeded()
        await self._publish_transition(serial, was_online, device.health.online)
        for message in zone_messages(
            self._config.base_topic, serial, device.zones, self._config.qos
        ):
            await self._transport.publish(message)

    async def _publish_transition(self, serial: str, was_online: bool, now_online: bool) -> None:
        if was_online != now_online:
            await self._transport.publish(
                device_status_message(self._config.base_topic, serial, now_online)
            )

    async def refresh_network(self, serial: str) -> None:
        device = self._devices[serial]
        device.info = await device.client.get_info()
        device.health = device.health.succeeded()
        wifi = parse_wifi(device.info.wifi)
        if wifi is None:
            return
        for message in network_messages(
            self._config.base_topic, serial, wifi, self._config.qos
        ):
            await self._transport.publish(message)
