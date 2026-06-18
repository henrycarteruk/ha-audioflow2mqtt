import asyncio

from audioflow2mqtt.discovery import DiscoveryProtocol, discover_devices, PING


class _FakeDevice(asyncio.DatagramProtocol):
    """Replies to a discovery PING, like a real Audioflow device would."""

    def connection_made(self, transport):
        self._transport = transport

    def datagram_received(self, data, addr):
        if data == PING:
            self._transport.sendto(b"pong", addr)


def test_discover_devices_over_loopback():
    async def go():
        loop = asyncio.get_running_loop()
        dev_transport, _ = await loop.create_datagram_endpoint(
            _FakeDevice, local_addr=("127.0.0.1", 0)
        )
        port = dev_transport.get_extra_info("sockname")[1]
        try:
            return await discover_devices(timeout=0.2, port=port, broadcast="127.0.0.1")
        finally:
            dev_transport.close()

    assert asyncio.run(go()) == ["127.0.0.1"]


def test_collects_responder_ip():
    proto = DiscoveryProtocol()
    proto.datagram_received(b"pong", ("10.0.0.5", 10499))
    assert proto.discovered == ["10.0.0.5"]


def test_dedupes_repeat_responses():
    proto = DiscoveryProtocol()
    proto.datagram_received(b"pong", ("10.0.0.5", 10499))
    proto.datagram_received(b"pong again", ("10.0.0.5", 10499))
    assert proto.discovered == ["10.0.0.5"]


def test_collects_multiple_distinct_responders_in_order():
    proto = DiscoveryProtocol()
    proto.datagram_received(b"pong", ("10.0.0.5", 10499))
    proto.datagram_received(b"pong", ("10.0.0.9", 10499))
    assert proto.discovered == ["10.0.0.5", "10.0.0.9"]
