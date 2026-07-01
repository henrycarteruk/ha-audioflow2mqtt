import asyncio

import httpx

from audioflow2mqtt.config import resolve_config
from audioflow2mqtt.device import AudioflowClient, DeviceInfo, Zone
from audioflow2mqtt.dispatch import ApplyZoneState, ApplyAllZones, ApplyZoneEnable
from audioflow2mqtt.app import Orchestrator, Device
from audioflow2mqtt.health import DeviceHealth


CONFIG = resolve_config({"base_topic": "af", "qos": 1})

INFO = DeviceInfo(serial="S", model="AF1", name="Living", fw_version="1.2", wifi="Net [6] (-58 dBm)")


class FakeTransport:
    def __init__(self):
        self.published = []
        self.subscribed = []

    async def publish(self, message):
        self.published.append(message)

    async def subscribe(self, topics):
        self.subscribed.extend(topics)


def make_device(handler, zones):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return Device(client=AudioflowClient("10.0.0.5", http), info=INFO, zones=zones), http


def _put_capture(puts):
    def handler(request):
        puts.append((request.method, request.url.path, request.content.decode()))
        return httpx.Response(200)
    return handler


def test_execute_apply_all_zones_calls_device():
    puts = []
    device, http = make_device(_put_capture(puts), [Zone(1, "K", "off", True)])
    orch = Orchestrator(CONFIG, FakeTransport(), {"S": device})

    async def go():
        try:
            await orch.execute(ApplyAllZones("S", True, 2))
        finally:
            await http.aclose()

    asyncio.run(go())
    assert ("PUT", "/zones", "1 1") in puts


def test_execute_apply_zone_enable_calls_device():
    puts = []
    device, http = make_device(_put_capture(puts), [Zone(1, "K", "off", True)])
    orch = Orchestrator(CONFIG, FakeTransport(), {"S": device})

    async def go():
        try:
            await orch.execute(ApplyZoneEnable("S", 1, False, "Kitchen"))
        finally:
            await http.aclose()

    asyncio.run(go())
    assert ("PUT", "/zonename/1", "0Kitchen") in puts


def test_refresh_state_publishes_zone_messages():
    def handler(request):
        assert request.url.path == "/zones"
        return httpx.Response(200, json={"zones": [{"name": "K", "state": "on", "enabled": 1}]})

    device, http = make_device(handler, [])
    transport = FakeTransport()
    orch = Orchestrator(CONFIG, transport, {"S": device})

    async def go():
        try:
            await orch.refresh_state("S")
        finally:
            await http.aclose()

    asyncio.run(go())
    published = [(m.topic, m.payload) for m in transport.published]
    assert ("af/S/zone_state/1", "on") in published
    assert ("af/S/zone_enabled/1", "1") in published


def test_handle_message_command_round_trip():
    puts = []

    def handler(request):
        if request.method == "PUT":
            puts.append((request.url.path, request.content.decode()))
            return httpx.Response(200)
        # GET /zones reflects the applied change
        return httpx.Response(200, json={"zones": [{"name": "Kitchen", "state": "on", "enabled": 1}]})

    device, http = make_device(handler, [Zone(1, "Kitchen", "off", True)])
    transport = FakeTransport()
    orch = Orchestrator(CONFIG, transport, {"S": device})

    async def go():
        try:
            await orch.handle_message("af/S/set_zone_state/1", "on")
        finally:
            await http.aclose()

    asyncio.run(go())
    assert ("/zones/1", "1") in puts  # command reached the device
    published = [(m.topic, m.payload) for m in transport.published]
    assert ("af/S/zone_state/1", "on") in published  # new state republished


def test_handle_message_ignores_unparseable_topic():
    device, http = make_device(lambda r: httpx.Response(500), [Zone(1, "K", "off", True)])
    transport = FakeTransport()
    orch = Orchestrator(CONFIG, transport, {"S": device})

    async def go():
        try:
            await orch.handle_message("af/S/zone_state/1", "on")  # not a command topic
        finally:
            await http.aclose()

    asyncio.run(go())
    assert transport.published == []  # nothing happened


def test_refresh_network_publishes_network_info():
    def handler(request):
        assert request.url.path == "/switch"
        return httpx.Response(200, json={
            "serial": "S", "model": "AF1", "name": "L", "version": "1.2",
            "wifi": "Net [6] (-58 dBm)",
        })

    device, http = make_device(handler, [])
    transport = FakeTransport()
    orch = Orchestrator(CONFIG, transport, {"S": device})

    async def go():
        try:
            await orch.refresh_network("S")
        finally:
            await http.aclose()

    asyncio.run(go())
    published = [(m.topic, m.payload) for m in transport.published]
    assert ("af/S/network_info/ssid", "Net") in published
    assert ("af/S/network_info/rssi", "-58") in published


def test_refresh_state_marks_offline_after_failures():
    device, http = make_device(lambda r: httpx.Response(500), [Zone(1, "K", "off", True)])
    device.health = DeviceHealth(failures=2, online=True)  # one failure from offline
    transport = FakeTransport()
    orch = Orchestrator(CONFIG, transport, {"S": device})

    async def go():
        try:
            await orch.refresh_state("S")
        finally:
            await http.aclose()

    asyncio.run(go())
    assert device.health.online is False
    published = [(m.topic, m.payload) for m in transport.published]
    assert ("af/S/status", "offline") in published


def test_on_connect_subscribes_and_publishes_discovery():
    device, http = make_device(lambda r: httpx.Response(200), [Zone(1, "Kitchen", "off", True)])
    transport = FakeTransport()
    orch = Orchestrator(CONFIG, transport, {"S": device})

    async def go():
        try:
            await orch.on_connect()
        finally:
            await http.aclose()

    asyncio.run(go())
    assert transport.subscribed == ["af/S/#", "af/discover"]
    published = [(m.topic, m.payload) for m in transport.published]
    assert ("af/status", "online") in published                       # gateway online
    assert ("af/S/status", "online") in published                     # device online
    topics = [m.topic for m in transport.published]
    assert "homeassistant/switch/S/1/config" in topics                # HA discovery


def test_rediscover_skips_unreachable_ip():
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    transport = FakeTransport()

    async def discover():
        return ["10.0.0.9"]

    orch = Orchestrator(CONFIG, transport, {}, http=http, discover=discover)

    async def go():
        try:
            await orch.rediscover()  # must not raise on an unreachable device
        finally:
            await http.aclose()

    asyncio.run(go())
    assert transport.published == []  # nothing announced for the unreachable IP


def test_rediscover_publishes_initial_state_for_new_device():
    def handler(request):
        if request.url.path == "/switch":
            return httpx.Response(200, json={
                "serial": "S2", "model": "AF1", "name": "New", "version": "1.0",
                "wifi": "Net [6] (-58 dBm)",
            })
        if request.url.path == "/zones":
            return httpx.Response(200, json={"zones": [{"name": "Z", "state": "on", "enabled": 1}]})
        return httpx.Response(200)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = FakeTransport()

    async def discover():
        return ["10.0.0.7"]

    orch = Orchestrator(CONFIG, transport, {}, http=http, discover=discover)

    async def go():
        try:
            await orch.rediscover()
        finally:
            await http.aclose()

    asyncio.run(go())
    published = [(m.topic, m.payload) for m in transport.published]
    assert ("af/S2/zone_state/1", "on") in published        # refresh_state ran
    assert ("af/S2/network_info/ssid", "Net") in published  # refresh_network ran


def test_discover_command_acquires_new_device():
    def handler(request):
        if request.url.path == "/switch":
            return httpx.Response(200, json={
                "serial": "S2", "model": "AF1", "name": "New", "version": "1.0",
                "wifi": "Net [6] (-58 dBm)",
            })
        if request.url.path == "/zones":
            return httpx.Response(200, json={"zones": [{"name": "Z", "state": "off", "enabled": 1}]})
        return httpx.Response(200)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = FakeTransport()

    async def discover():
        return ["10.0.0.7"]

    orch = Orchestrator(CONFIG, transport, {}, http=http, discover=discover)

    async def go():
        try:
            await orch.handle_message("af/discover", "")
        finally:
            await http.aclose()

    asyncio.run(go())
    assert "af/S2/#" in transport.subscribed
    topics = [m.topic for m in transport.published]
    assert "homeassistant/switch/S2/1/config" in topics
    published = [(m.topic, m.payload) for m in transport.published]
    assert ("af/S2/status", "online") in published


def test_handle_message_reboot_calls_device_and_skips_state_poll():
    gets = []

    def handler(request):
        gets.append(request.url.path)
        return httpx.Response(200, text="rebooting")

    device, http = make_device(handler, [Zone(1, "K", "off", True)])
    transport = FakeTransport()
    orch = Orchestrator(CONFIG, transport, {"S": device})

    async def go():
        try:
            await orch.handle_message("af/S/reboot", "")
        finally:
            await http.aclose()

    asyncio.run(go())
    assert "/reboot_now" in gets
    assert transport.published == []  # no state republish after reboot


def test_execute_apply_zone_state_calls_device():
    puts = []

    def handler(request):
        puts.append((request.method, request.url.path, request.content.decode()))
        return httpx.Response(200)

    device, http = make_device(handler, [Zone(1, "Kitchen", "off", True)])
    orch = Orchestrator(CONFIG, FakeTransport(), {"S": device})

    async def go():
        try:
            await orch.execute(ApplyZoneState("S", 1, True))
        finally:
            await http.aclose()

    asyncio.run(go())
    assert ("PUT", "/zones/1", "1") in puts
