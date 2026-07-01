import json

from audioflow2mqtt.ha_discovery import build_device_discovery
from audioflow2mqtt.device import DeviceInfo, Zone


def _by_topic(messages, topic):
    return next(m for m in messages if m.topic == topic)


def _payload(message):
    return json.loads(message.payload)


INFO = DeviceInfo(serial="0123456789", model="AF1", name="Living Room", fw_version="1.2", wifi="")
ZONES = [Zone(number=1, name="Kitchen", state="on", enabled=True)]


def test_disabled_zone_gets_disabled_suffix():
    zones = [
        Zone(number=1, name="Kitchen", state="on", enabled=True),
        Zone(number=2, name="Patio", state="off", enabled=False),
    ]
    msgs = build_device_discovery("audioflow2mqtt", INFO, zones)
    assert _payload(_by_topic(msgs, "homeassistant/switch/0123456789/1/config"))["name"] == "Kitchen speakers"
    assert _payload(_by_topic(msgs, "homeassistant/switch/0123456789/2/config"))["name"] == "Patio speakers (Disabled)"


def test_all_zones_buttons():
    msgs = build_device_discovery("audioflow2mqtt", INFO, ZONES)
    on = _payload(_by_topic(msgs, "homeassistant/button/0123456789/all_zones_on/config"))
    off = _payload(_by_topic(msgs, "homeassistant/button/0123456789/all_zones_off/config"))
    assert on["command_topic"] == "audioflow2mqtt/0123456789/set_zone_state"
    assert on["payload_press"] == "on"
    assert on["unique_id"] == "0123456789_all_zones_on"
    assert off["payload_press"] == "off"
    assert off["unique_id"] == "0123456789_all_zones_off"


def test_network_info_sensors():
    msgs = build_device_discovery("audioflow2mqtt", INFO, ZONES)
    ssid = _payload(_by_topic(msgs, "homeassistant/sensor/0123456789/ssid/config"))
    channel = _payload(_by_topic(msgs, "homeassistant/sensor/0123456789/channel/config"))
    rssi = _payload(_by_topic(msgs, "homeassistant/sensor/0123456789/rssi/config"))
    assert ssid["state_topic"] == "audioflow2mqtt/0123456789/network_info/ssid"
    assert ssid["name"] == "SSID"
    assert channel["name"] == "Wi-Fi channel"
    assert rssi["name"] == "RSSI"
    assert rssi["unique_id"] == "0123456789rssi"


def test_all_messages_share_availability_and_device():
    msgs = build_device_discovery("audioflow2mqtt", INFO, ZONES)
    assert msgs
    for m in msgs:
        assert m.qos == 1
        assert m.retain is True
        payload = _payload(m)
        assert payload["availability"] == [
            {"topic": "audioflow2mqtt/status"},
            {"topic": "audioflow2mqtt/0123456789/status"},
        ]
        assert payload["device"] == {
            "name": "Living Room",
            "identifiers": "0123456789",
            "manufacturer": "Audioflow",
            "model": "AF1",
            "sw_version": "1.2",
        }
        assert payload["platform"] == "mqtt"


def test_reboot_button():
    msgs = build_device_discovery("audioflow2mqtt", INFO, ZONES)
    rb = _payload(_by_topic(msgs, "homeassistant/button/0123456789/reboot/config"))
    assert rb["command_topic"] == "audioflow2mqtt/0123456789/reboot"
    assert rb["payload_press"] == "reboot"
    assert rb["unique_id"] == "0123456789_reboot"
    assert rb["icon"] == "mdi:restart"


def test_switch_message_per_zone():
    msgs = build_device_discovery("audioflow2mqtt", INFO, ZONES)
    sw = _payload(_by_topic(msgs, "homeassistant/switch/0123456789/1/config"))
    assert sw["command_topic"] == "audioflow2mqtt/0123456789/set_zone_state/1"
    assert sw["state_topic"] == "audioflow2mqtt/0123456789/zone_state/1"
    assert sw["unique_id"] == "01234567891"
    assert sw["name"] == "Kitchen speakers"
