"""Async aiomqtt transport: connect (with LWT), subscribe, publish, receive.

Thin wrapper around aiomqtt. The client factory is injected so the transport
can be exercised with a fake client; production uses aiomqtt.Client. The pure
publish/subscribe/will builders live in mqtt.py.
"""
from __future__ import annotations

import asyncio

import aiomqtt

from .config import Config
from .mqtt import gateway_will


class MqttTransport:
    def __init__(self, config: Config, *, client_factory=aiomqtt.Client):
        self._config = config
        self._factory = client_factory
        self._client = None
        self._stop = False

    async def connect(self) -> None:
        will = gateway_will(self._config.base_topic)
        client = self._factory(
            hostname=self._config.mqtt_host,
            port=self._config.mqtt_port,
            username=self._config.mqtt_user,
            password=self._config.mqtt_pass,
            identifier=self._config.base_topic,
            will=aiomqtt.Will(
                topic=will.topic, payload=will.payload, qos=will.qos, retain=will.retain
            ),
        )
        await client.__aenter__()
        self._client = client

    async def publish(self, message) -> None:
        await self._client.publish(
            message.topic, message.payload, qos=message.qos, retain=message.retain
        )

    async def subscribe(self, topics: list[str]) -> None:
        for topic in topics:
            await self._client.subscribe(topic)

    async def messages(self):
        async for message in self._client.messages:
            yield str(message.topic), message.payload.decode()

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None

    def stop(self) -> None:
        self._stop = True

    async def run_forever(self, on_message, *, backoff: float = 3.0, on_connect=None) -> None:
        """Connect and dispatch messages, reconnecting on MqttError until stopped."""
        while not self._stop:
            try:
                await self.connect()
                if on_connect is not None:
                    await on_connect(self)
                async for topic, payload in self.messages():
                    await on_message(topic, payload)
                    if self._stop:
                        break
            except aiomqtt.MqttError:
                await asyncio.sleep(backoff)
            finally:
                await self.disconnect()
