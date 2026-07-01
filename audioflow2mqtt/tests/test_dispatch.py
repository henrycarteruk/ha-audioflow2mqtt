from audioflow2mqtt.commands import SetZoneState, SetAllZones, SetZoneEnable, Reboot, Discover
from audioflow2mqtt.device import Zone
from audioflow2mqtt.dispatch import (
    plan_action,
    ApplyZoneState,
    ApplyAllZones,
    ApplyZoneEnable,
)


ZONES = [
    Zone(number=1, name="Kitchen", state="off", enabled=True),
    Zone(number=2, name="Patio", state="on", enabled=True),
]


def test_toggle_flips_current_state():
    # zone 2 is currently "on" -> toggle turns it off
    assert plan_action(SetZoneState("S", 2, "toggle"), ZONES) == ApplyZoneState("S", 2, False)
    # zone 1 is currently "off" -> toggle turns it on
    assert plan_action(SetZoneState("S", 1, "toggle"), ZONES) == ApplyZoneState("S", 1, True)


def test_unknown_zone_is_rejected():
    assert plan_action(SetZoneState("S", 5, "on"), ZONES) is None


def test_disabled_zone_is_rejected():
    zones = [Zone(number=3, name="Garage", state="off", enabled=False)]
    assert plan_action(SetZoneState("S", 3, "on"), zones) is None


def test_set_all_zones_uses_zone_count():
    assert plan_action(SetAllZones("S", "on"), ZONES) == ApplyAllZones("S", True, 2)
    assert plan_action(SetAllZones("S", "off"), ZONES) == ApplyAllZones("S", False, 2)


def test_set_zone_enable_echoes_current_name():
    # disabling zone 1 ("Kitchen"); name must be echoed back for the device
    assert plan_action(SetZoneEnable("S", 1, 0), ZONES) == ApplyZoneEnable(
        serial="S", zone=1, enabled=False, name="Kitchen"
    )
    assert plan_action(SetZoneEnable("S", 1, 1), ZONES) == ApplyZoneEnable(
        serial="S", zone=1, enabled=True, name="Kitchen"
    )


def test_discover_returns_discover():
    assert plan_action(Discover(), None) == Discover()


def test_reboot_returns_command_when_device_known():
    assert plan_action(Reboot("S"), ZONES) == Reboot("S")


def test_reboot_returns_none_when_device_unknown():
    assert plan_action(Reboot("S"), None) is None


def test_explicit_on_plans_apply_zone_state():
    action = plan_action(SetZoneState(serial="S", zone=1, value="on"), ZONES)
    assert action == ApplyZoneState(serial="S", zone=1, on=True)
