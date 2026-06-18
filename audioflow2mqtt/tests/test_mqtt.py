from audioflow2mqtt.device import Zone
from audioflow2mqtt.wifi import WifiInfo
from audioflow2mqtt.mqtt import (
    PublishMessage,
    zone_messages,
    network_messages,
    device_status_message,
    gateway_status_message,
    subscribe_topics,
    gateway_will,
)


ZONES = [
    Zone(number=1, name="Kitchen", state="on", enabled=True),
    Zone(number=2, name="Patio", state="off", enabled=False),
]


def test_device_status_message_is_retained():
    online = device_status_message("audioflow2mqtt", "0123456789", True)
    assert online == PublishMessage(
        "audioflow2mqtt/0123456789/status", "online", qos=1, retain=True
    )
    offline = device_status_message("audioflow2mqtt", "0123456789", False)
    assert offline.payload == "offline"


def test_gateway_status_message():
    assert gateway_status_message("audioflow2mqtt", True) == PublishMessage(
        "audioflow2mqtt/status", "online", qos=1, retain=True
    )
    assert gateway_status_message("audioflow2mqtt", False).payload == "offline"


def test_gateway_will_is_offline_status():
    # LWT the broker publishes if the gateway drops; mirrors gateway offline status.
    assert gateway_will("audioflow2mqtt") == PublishMessage(
        "audioflow2mqtt/status", "offline", qos=1, retain=True
    )


def test_subscribe_topics():
    topics = subscribe_topics("audioflow2mqtt", ["0123456789", "9876543210"])
    assert topics == [
        "audioflow2mqtt/0123456789/#",
        "audioflow2mqtt/9876543210/#",
        "audioflow2mqtt/discover",
    ]


def test_network_messages():
    wifi = WifiInfo(ssid="Net", channel=6, rssi=-58)
    msgs = network_messages("audioflow2mqtt", "0123456789", wifi, qos=1)
    assert msgs == [
        PublishMessage("audioflow2mqtt/0123456789/network_info/ssid", "Net", qos=1),
        PublishMessage("audioflow2mqtt/0123456789/network_info/channel", "6", qos=1),
        PublishMessage("audioflow2mqtt/0123456789/network_info/rssi", "-58", qos=1),
    ]


def test_zone_messages():
    msgs = zone_messages("audioflow2mqtt", "0123456789", ZONES, qos=1)
    assert msgs == [
        PublishMessage("audioflow2mqtt/0123456789/zone_state/1", "on", qos=1),
        PublishMessage("audioflow2mqtt/0123456789/zone_enabled/1", "1", qos=1),
        PublishMessage("audioflow2mqtt/0123456789/zone_state/2", "off", qos=1),
        PublishMessage("audioflow2mqtt/0123456789/zone_enabled/2", "0", qos=1),
    ]
