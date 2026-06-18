from audioflow2mqtt.ha_discovery import (
    build_device_discovery,
    DiscoveryDevice,
    DiscoveryZone,
)


def _by_topic(messages, topic):
    return next(m for m in messages if m.topic == topic)


DEVICE = DiscoveryDevice(
    serial="0123456789",
    name="Living Room",
    model="AF1",
    fw_version="1.2",
    zones=[DiscoveryZone(number=1, name="Kitchen", enabled=True)],
)


def test_disabled_zone_gets_disabled_suffix():
    device = DiscoveryDevice(
        serial="0123456789",
        name="Living Room",
        model="AF1",
        fw_version="1.2",
        zones=[
            DiscoveryZone(number=1, name="Kitchen", enabled=True),
            DiscoveryZone(number=2, name="Patio", enabled=False),
        ],
    )
    msgs = build_device_discovery("audioflow2mqtt", device)
    assert _by_topic(msgs, "homeassistant/switch/0123456789/1/config").payload["name"] == "Kitchen speakers"
    assert _by_topic(msgs, "homeassistant/switch/0123456789/2/config").payload["name"] == "Patio speakers (Disabled)"


def test_all_zones_buttons():
    msgs = build_device_discovery("audioflow2mqtt", DEVICE)
    on = _by_topic(msgs, "homeassistant/button/0123456789/all_zones_on/config")
    off = _by_topic(msgs, "homeassistant/button/0123456789/all_zones_off/config")
    assert on.payload["command_topic"] == "audioflow2mqtt/0123456789/set_zone_state"
    assert on.payload["payload_press"] == "on"
    assert on.payload["unique_id"] == "0123456789_all_zones_on"
    assert off.payload["payload_press"] == "off"
    assert off.payload["unique_id"] == "0123456789_all_zones_off"


def test_network_info_sensors():
    msgs = build_device_discovery("audioflow2mqtt", DEVICE)
    ssid = _by_topic(msgs, "homeassistant/sensor/0123456789/ssid/config")
    channel = _by_topic(msgs, "homeassistant/sensor/0123456789/channel/config")
    rssi = _by_topic(msgs, "homeassistant/sensor/0123456789/rssi/config")
    assert ssid.payload["state_topic"] == "audioflow2mqtt/0123456789/network_info/ssid"
    assert ssid.payload["name"] == "SSID"
    assert channel.payload["name"] == "Wi-Fi channel"
    assert rssi.payload["name"] == "RSSI"
    assert rssi.payload["unique_id"] == "0123456789rssi"


def test_all_messages_share_availability_and_device():
    msgs = build_device_discovery("audioflow2mqtt", DEVICE)
    assert msgs
    for m in msgs:
        assert m.payload["availability"] == [
            {"topic": "audioflow2mqtt/status"},
            {"topic": "audioflow2mqtt/0123456789/status"},
        ]
        assert m.payload["device"] == {
            "name": "Living Room",
            "identifiers": "0123456789",
            "manufacturer": "Audioflow",
            "model": "AF1",
            "sw_version": "1.2",
        }
        assert m.payload["platform"] == "mqtt"


def test_switch_message_per_zone():
    msgs = build_device_discovery("audioflow2mqtt", DEVICE)
    sw = _by_topic(msgs, "homeassistant/switch/0123456789/1/config")
    assert sw.payload["command_topic"] == "audioflow2mqtt/0123456789/set_zone_state/1"
    assert sw.payload["state_topic"] == "audioflow2mqtt/0123456789/zone_state/1"
    assert sw.payload["unique_id"] == "01234567891"
    assert sw.payload["name"] == "Kitchen speakers"
