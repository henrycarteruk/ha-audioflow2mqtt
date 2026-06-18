"""UDP broadcast discovery of Audioflow devices on the local network.

Broadcasts a ping and collects the IP addresses of responders. The protocol
that accumulates responders is separated from the socket I/O so it can be
tested without a network.
"""
from __future__ import annotations

import asyncio
import socket

PING = b"afping"
DISCOVERY_PORT = 10499


class DiscoveryProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.discovered: list[str] = []

    def datagram_received(self, data: bytes, addr) -> None:
        ip = addr[0]
        if ip not in self.discovered:
            self.discovered.append(ip)


async def discover_devices(
    timeout: float = 3.0,
    port: int = DISCOVERY_PORT,
    broadcast: str = "255.255.255.255",
) -> list[str]:
    """Broadcast a ping and return the IPs that respond within `timeout`."""
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        DiscoveryProtocol, family=socket.AF_INET, allow_broadcast=True
    )
    try:
        for _ in range(3):
            transport.sendto(PING, (broadcast, port))
            await asyncio.sleep(0.02)
        await asyncio.sleep(timeout)
        return list(protocol.discovered)
    finally:
        transport.close()
