"""Entrypoint: build real dependencies and run the Orchestrator.

This module is intentionally thin glue — all decision logic lives in the
unit-tested modules (config, dispatch, app, mqtt, mqtt_transport, ...).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys

import httpx

from .app import Device, Orchestrator
from .config import fetch_mqtt_service, resolve_config
from .discovery import discover_devices
from .mqtt_transport import MqttTransport

POLL_STATE_SECONDS = 10
POLL_NETWORK_SECONDS = 60
DISCOVERY_RETRY_SECONDS = 60
HEALTH_PORT = 8099


async def _health_server(transport: MqttTransport, devices: dict) -> None:
    async def handle(reader, writer):
        raw = await reader.read(1024)
        path = raw.split(b" ")[1].split(b"?")[0] if b" " in raw else b"/"
        if path == b"/health":
            ok = transport.connected
            writer.write(b"HTTP/1.1 " + (b"200 OK" if ok else b"503 Service Unavailable") + b"\r\nContent-Type: text/plain\r\n\r\n" + (b"OK" if ok else b"Service Unavailable"))
        else:
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + _status_page(transport.connected, devices))
        await writer.drain()
        writer.close()
    server = await asyncio.start_server(handle, "0.0.0.0", HEALTH_PORT)
    async with server:
        await server.serve_forever()


def _status_page(connected: bool, devices: dict) -> bytes:
    rows = []
    for device in devices.values():
        rows.append(
            f"<tr><td colspan='3'><strong>{device.info.name}</strong> "
            f"<small>{device.info.model} · {device.info.serial}</small> "
            f"<span style='color:{'#2ecc71' if device.health.online else '#e74c3c'}'>{'online' if device.health.online else 'offline'}</span></td></tr>"
        )
        for zone in device.zones:
            rows.append(
                f"<tr><td style='padding-left:1.5rem'>Zone {zone.number}</td>"
                f"<td>{zone.name}{'' if zone.enabled else ' <small>(disabled)</small>'}</td>"
                f"<td style='color:{'#2ecc71' if zone.state == 'on' else '#aaa'}'>{zone.state}</td></tr>"
            )
    table = (
        "<table><thead><tr><th>Zone</th><th>Name</th><th>State</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
        if rows else "<p>No devices discovered yet.</p>"
    )
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Audioflow2MQTT</title>
<style>
  body{{font-family:sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;color:#333}}
  h1{{font-size:1.4rem;margin-bottom:.25rem}}
  .badge{{display:inline-block;padding:.2rem .6rem;border-radius:.25rem;color:#fff;font-size:.85rem}}
  table{{width:100%;border-collapse:collapse;margin-top:1.5rem}}
  th{{text-align:left;border-bottom:2px solid #ddd;padding:.4rem .5rem}}
  td{{padding:.35rem .5rem;border-bottom:1px solid #eee}}
</style>
</head><body>
<h1>Audioflow2MQTT</h1>
<span class="badge" style="background:{'#2ecc71' if connected else '#e74c3c'}">MQTT {'Connected' if connected else 'Disconnected'}</span>
{table}
</body></html>"""
    return html.encode()


async def _poll(devices, interval: int, refresh) -> None:
    while True:
        await asyncio.sleep(interval)
        for serial in list(devices):
            await refresh(serial)


async def run() -> None:
    with open("/data/options.json") as f:
        options = json.load(f)
    config = resolve_config(options, None)
    logging.basicConfig(
        level=config.log_level.upper(), format="%(asctime)s %(levelname)s: %(message)s"
    )
    logging.info("=== audioflow2mqtt starting ===")

    async with httpx.AsyncClient(timeout=3) as http:
        # Supervisor MQTT service fills broker config when not set explicitly.
        service = await fetch_mqtt_service(http, os.environ.get("SUPERVISOR_TOKEN"))
        config = resolve_config(options, service)
        if config.mqtt_host is None:
            logging.error("No MQTT broker configured or discoverable; exiting.")
            sys.exit(1)

        async def device_source() -> list[str]:
            # Explicit IPs if configured, otherwise UDP discovery. Used for the
            # initial acquisition and every background retry, so configured IPs
            # that are unreachable at startup are simply retried, not fatal.
            return list(config.devices) if config.devices else await discover_devices()

        devices: dict[str, Device] = {}
        transport = MqttTransport(config)
        orchestrator = Orchestrator(config, transport, devices, http=http, discover=device_source)

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, transport.stop)

        async def _retry() -> None:
            while True:
                await asyncio.sleep(DISCOVERY_RETRY_SECONDS)
                await orchestrator.rediscover()

        async def on_connect(_transport) -> None:
            # Re-establish already-known devices, then acquire any new ones
            # (on the first connect every device is "new").
            await orchestrator.on_connect()
            for serial in list(devices):
                await orchestrator.refresh_state(serial)
                await orchestrator.refresh_network(serial)
            await orchestrator.rediscover()

        tasks = [
            asyncio.create_task(_poll(devices, POLL_STATE_SECONDS, orchestrator.refresh_state)),
            asyncio.create_task(_poll(devices, POLL_NETWORK_SECONDS, orchestrator.refresh_network)),
            asyncio.create_task(_retry()),
            asyncio.create_task(_health_server(transport, devices)),
        ]
        try:
            await transport.run_forever(orchestrator.handle_message, on_connect=on_connect)
        finally:
            for task in tasks:
                task.cancel()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
