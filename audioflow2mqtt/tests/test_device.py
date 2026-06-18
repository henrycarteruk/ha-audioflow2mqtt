import asyncio

import httpx
import pytest

from audioflow2mqtt.device import AudioflowClient, DeviceInfo, Zone


def _run_with(handler, action):
    """Drive an async client action against a MockTransport-backed device."""
    async def go():
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = AudioflowClient("10.0.0.5", http)
        try:
            return await action(client)
        finally:
            await http.aclose()

    return asyncio.run(go())


def test_get_zones_parses_zones():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/zones"
        return httpx.Response(200, json={"zones": [
            {"name": "Kitchen", "state": "on", "enabled": 1},
            {"name": "Patio", "state": "off", "enabled": 0},
        ]})

    zones = _run_with(handler, lambda c: c.get_zones())
    assert zones == [
        Zone(number=1, name="Kitchen", state="on", enabled=True),
        Zone(number=2, name="Patio", state="off", enabled=False),
    ]


def _capture(seen):
    def handler(request):
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = request.content.decode()
        return httpx.Response(200)
    return handler


def test_set_zone_state_puts_zone():
    on = {}
    _run_with(_capture(on), lambda c: c.set_zone_state(2, True))
    assert on["method"] == "PUT"
    assert on["path"] == "/zones/2"
    assert on["body"] == "1"

    off = {}
    _run_with(_capture(off), lambda c: c.set_zone_state(2, False))
    assert off["body"] == "0"


def test_set_all_zones_matches_zone_count():
    on = {}
    _run_with(_capture(on), lambda c: c.set_all_zones(True, 4))
    assert on["method"] == "PUT"
    assert on["path"] == "/zones"
    assert on["body"] == "1 1 1 1"

    off = {}
    _run_with(_capture(off), lambda c: c.set_all_zones(False, 2))
    assert off["body"] == "0 0"


def test_set_zone_enable_echoes_name():
    seen = {}
    _run_with(_capture(seen), lambda c: c.set_zone_enable(1, True, "Kitchen"))
    assert seen["method"] == "PUT"
    assert seen["path"] == "/zonename/1"
    assert seen["body"] == "1Kitchen"

    disabled = {}
    _run_with(_capture(disabled), lambda c: c.set_zone_enable(1, False, "Kitchen"))
    assert disabled["body"] == "0Kitchen"


def test_non_2xx_response_raises():
    def handler(request):
        return httpx.Response(500)

    with pytest.raises(httpx.HTTPStatusError):
        _run_with(handler, lambda c: c.get_info())
    with pytest.raises(httpx.HTTPStatusError):
        _run_with(handler, lambda c: c.set_zone_state(1, True))


def test_get_info_parses_switch():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/switch"
        return httpx.Response(200, json={
            "serial": "0123456789",
            "model": "AF1",
            "name": "Living Room",
            "version": "1.2",
            "wifi": "Net [6] (-58 dBm)",
        })

    info = _run_with(handler, lambda c: c.get_info())
    assert info == DeviceInfo(
        serial="0123456789",
        model="AF1",
        name="Living Room",
        fw_version="1.2",
        wifi="Net [6] (-58 dBm)",
    )
