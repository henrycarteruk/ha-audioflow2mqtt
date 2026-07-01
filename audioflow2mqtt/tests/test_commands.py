from audioflow2mqtt.commands import (
    parse_command,
    SetZoneState,
    SetAllZones,
    SetZoneEnable,
    Reboot,
    Discover,
)


def test_set_zone_state_for_single_zone():
    cmd = parse_command(
        "audioflow2mqtt", "audioflow2mqtt/0123456789/set_zone_state/2", "on"
    )
    assert cmd == SetZoneState(serial="0123456789", zone=2, value="on")


def test_too_short_topic_is_ignored():
    assert parse_command("audioflow2mqtt", "audioflow2mqtt", "on") is None


def test_invalid_zone_state_value_is_rejected():
    cmd = parse_command(
        "audioflow2mqtt", "audioflow2mqtt/0123456789/set_zone_state/2", "banana"
    )
    assert cmd is None


def test_non_numeric_enable_payload_is_rejected():
    cmd = parse_command(
        "audioflow2mqtt", "audioflow2mqtt/0123456789/set_zone_enable/1", "x"
    )
    assert cmd is None


def test_toggle_is_rejected_for_all_zones():
    cmd = parse_command(
        "audioflow2mqtt", "audioflow2mqtt/0123456789/set_zone_state", "toggle"
    )
    assert cmd is None


def test_wrong_base_topic_is_ignored():
    cmd = parse_command(
        "audioflow2mqtt", "other/0123456789/set_zone_state/2", "on"
    )
    assert cmd is None


def test_unknown_command_is_ignored():
    cmd = parse_command(
        "audioflow2mqtt", "audioflow2mqtt/0123456789/zone_state/2", "on"
    )
    assert cmd is None


def test_gateway_discover_topic():
    cmd = parse_command("audioflow2mqtt", "audioflow2mqtt/discover", "")
    assert cmd == Discover()


def test_set_zone_enable():
    cmd = parse_command(
        "audioflow2mqtt", "audioflow2mqtt/0123456789/set_zone_enable/1", "0"
    )
    assert cmd == SetZoneEnable(serial="0123456789", zone=1, enabled=0)


def test_multi_digit_zone_parses_fully():
    # Regression guard: the old parser took only the last topic char (topic[-1:]),
    # so zone 12 became zone 2. The whole segment must be used.
    cmd = parse_command(
        "audioflow2mqtt", "audioflow2mqtt/0123456789/set_zone_state/12", "on"
    )
    assert cmd == SetZoneState(serial="0123456789", zone=12, value="on")


def test_set_zone_state_without_zone_targets_all_zones():
    cmd = parse_command(
        "audioflow2mqtt", "audioflow2mqtt/0123456789/set_zone_state", "off"
    )
    assert cmd == SetAllZones(serial="0123456789", value="off")


def test_reboot_topic_parses_to_reboot():
    cmd = parse_command("audioflow2mqtt", "audioflow2mqtt/0123456789/reboot", "")
    assert cmd == Reboot(serial="0123456789")
