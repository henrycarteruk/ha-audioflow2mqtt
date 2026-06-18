"""Pure builders for outbound MQTT publishes and subscriptions.

Turns domain state (zones, Wi-Fi info, status) into PublishMessages and
computes the topics to subscribe to and the LWT will. No I/O: the async
transport layer (built with orchestration) consumes these.
"""
from __future__ import annotations

from dataclasses import dataclass

from .device import Zone
from .wifi import WifiInfo


@dataclass(frozen=True)
class PublishMessage:
    topic: str
    payload: str
    qos: int = 0
    retain: bool = False


def zone_messages(base_topic: str, serial: str, zones: list[Zone], qos: int) -> list[PublishMessage]:
    messages: list[PublishMessage] = []
    for zone in zones:
        prefix = f"{base_topic}/{serial}"
        messages.append(PublishMessage(f"{prefix}/zone_state/{zone.number}", zone.state, qos=qos))
        messages.append(PublishMessage(
            f"{prefix}/zone_enabled/{zone.number}", "1" if zone.enabled else "0", qos=qos
        ))
    return messages


def network_messages(base_topic: str, serial: str, wifi: WifiInfo, qos: int) -> list[PublishMessage]:
    prefix = f"{base_topic}/{serial}/network_info"
    return [
        PublishMessage(f"{prefix}/ssid", wifi.ssid, qos=qos),
        PublishMessage(f"{prefix}/channel", str(wifi.channel), qos=qos),
        PublishMessage(f"{prefix}/rssi", str(wifi.rssi), qos=qos),
    ]


def _status_message(topic: str, online: bool) -> PublishMessage:
    return PublishMessage(topic, "online" if online else "offline", qos=1, retain=True)


def device_status_message(base_topic: str, serial: str, online: bool) -> PublishMessage:
    return _status_message(f"{base_topic}/{serial}/status", online)


def gateway_status_message(base_topic: str, online: bool) -> PublishMessage:
    return _status_message(f"{base_topic}/status", online)


def subscribe_topics(base_topic: str, serials: list[str]) -> list[str]:
    return [f"{base_topic}/{serial}/#" for serial in serials] + [f"{base_topic}/discover"]


def gateway_will(base_topic: str) -> PublishMessage:
    """Last-will: published by the broker if the gateway drops off."""
    return gateway_status_message(base_topic, online=False)
