import asyncio

import aiomqtt

from audioflow2mqtt.config import resolve_config
from audioflow2mqtt.mqtt import PublishMessage
from audioflow2mqtt.mqtt_transport import MqttTransport


class FakeMessage:
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload


class FakeClient:
    def __init__(self):
        self.entered = False
        self.exited = False
        self.published = []
        self.subscribed = []
        self._messages = []

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, *exc):
        self.exited = True

    async def publish(self, topic, payload, qos=0, retain=False):
        self.published.append((topic, payload, qos, retain))

    async def subscribe(self, topic):
        self.subscribed.append(topic)

    @property
    def messages(self):
        async def gen():
            for m in self._messages:
                yield m
        return gen()


def _capturing_factory(captured, client):
    def factory(**kwargs):
        captured.update(kwargs)
        return client
    return factory


CONFIG = resolve_config({
    "mqtt_host": "broker",
    "mqtt_port": 1884,
    "mqtt_user": "u",
    "mqtt_pass": "p",
    "base_topic": "af",
})


def test_publish_delegates_to_client():
    client = FakeClient()
    transport = MqttTransport(CONFIG, client_factory=lambda **k: client)

    async def go():
        await transport.connect()
        await transport.publish(PublishMessage("af/x", "hi", qos=1, retain=True))

    asyncio.run(go())
    assert client.published == [("af/x", "hi", 1, True)]


def test_subscribe_delegates_per_topic():
    client = FakeClient()
    transport = MqttTransport(CONFIG, client_factory=lambda **k: client)

    async def go():
        await transport.connect()
        await transport.subscribe(["a/#", "b/#"])

    asyncio.run(go())
    assert client.subscribed == ["a/#", "b/#"]


def test_messages_yields_decoded_topic_payload():
    client = FakeClient()
    client._messages = [
        FakeMessage("af/0123/set_zone_state/1", b"on"),
        FakeMessage("af/discover", b""),
    ]
    transport = MqttTransport(CONFIG, client_factory=lambda **k: client)

    async def go():
        await transport.connect()
        return [pair async for pair in transport.messages()]

    assert asyncio.run(go()) == [
        ("af/0123/set_zone_state/1", "on"),
        ("af/discover", ""),
    ]


def test_disconnect_exits_client():
    client = FakeClient()
    transport = MqttTransport(CONFIG, client_factory=lambda **k: client)

    async def go():
        await transport.connect()
        await transport.disconnect()

    asyncio.run(go())
    assert client.exited is True


class ErrorOnEnter:
    async def __aenter__(self):
        raise aiomqtt.MqttError("connection refused")

    async def __aexit__(self, *exc):
        pass


def test_reconnect_retries_on_mqtt_error():
    good = FakeClient()
    good._messages = [FakeMessage("af/discover", b"")]
    clients = [ErrorOnEnter(), good]
    transport = MqttTransport(CONFIG, client_factory=lambda **k: clients.pop(0))

    seen = []

    async def on_message(topic, payload):
        seen.append((topic, payload))
        transport.stop()

    asyncio.run(transport.run_forever(on_message, backoff=0))

    assert seen == [("af/discover", "")]   # recovered after the first attempt errored
    assert clients == []                   # both the failing and the good client were used


def test_connect_builds_client_with_conn_params_and_will():
    captured = {}
    client = FakeClient()
    transport = MqttTransport(CONFIG, client_factory=_capturing_factory(captured, client))

    asyncio.run(transport.connect())

    assert captured["hostname"] == "broker"
    assert captured["port"] == 1884
    assert captured["username"] == "u"
    assert captured["password"] == "p"
    assert captured["identifier"] == "af"
    assert captured["will"].topic == "af/status"
    assert captured["will"].payload == "offline"
    assert captured["will"].retain is True
    assert client.entered is True
