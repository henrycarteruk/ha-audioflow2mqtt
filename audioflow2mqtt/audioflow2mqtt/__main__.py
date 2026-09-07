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
from urllib.parse import parse_qs

import httpx

from .app import Device, Orchestrator
from .config import fetch_mqtt_service, resolve_config
from .discovery import discover_devices
from .dispatch import ApplyZoneState
from .mqtt_transport import MqttTransport

POLL_STATE_SECONDS = 10
POLL_NETWORK_SECONDS = 60
DISCOVERY_RETRY_SECONDS = 60
HEALTH_PORT = 8099

# Product photos keyed by zone count, for the status page — Audioflow's device
# lineup differs by zone count (2Z/3Z/4Z), not by the model string the device
# itself reports (whose exact format isn't documented).
MODEL_PHOTOS = {
    2: "https://flow.audio/cdn/shop/files/3S-2ZFrontStraightAudioflow.jpg?v=1730462563&width=330",
    3: "https://flow.audio/cdn/shop/files/3S-3ZFrontStraightAudioflow.jpg?v=1730584842&width=330",
    4: "https://flow.audio/cdn/shop/files/3S-4ZFrontStraightAudioflow.jpg?v=1730585084&width=330",
}


async def _health_server(transport: MqttTransport, devices: dict, execute, refresh_state) -> None:
    async def handle(reader, writer):
        method, _, request = (await reader.readline()).decode().partition(" ")
        path = request.split(" ")[0].split("?")[0]
        headers = {}
        while (line := (await reader.readline()).strip()):
            key, _, value = line.decode().partition(":")
            headers[key.strip().lower()] = value.strip()
        body = await reader.read(int(headers.get("content-length", 0)))
        peer = writer.get_extra_info("peername")[0]

        if path == "/health":
            ok = transport.connected
            writer.write(b"HTTP/1.1 " + (b"200 OK" if ok else b"503 Service Unavailable") + b"\r\nContent-Type: text/plain\r\n\r\n" + (b"OK" if ok else b"Service Unavailable"))
        elif peer != "172.30.32.2":
            writer.write(b"HTTP/1.1 403 Forbidden\r\n\r\n")
        elif method == "POST" and path == "/toggle":
            await _handle_toggle(body.decode(), devices, execute, refresh_state)
            # Relative redirect: Home Assistant's ingress proxy forwards requests to
            # the add-on with the per-session path prefix already stripped, so an
            # absolute "/" would send the browser to HA's own root instead of back
            # through the proxy. "./" resolves against the request URL and stays
            # under the ingress prefix.
            writer.write(b"HTTP/1.1 303 See Other\r\nLocation: ./\r\n\r\n")
        else:
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + _status_page(transport.connected, devices))
        await writer.drain()
        writer.close()
    server = await asyncio.start_server(handle, "0.0.0.0", HEALTH_PORT)
    async with server:
        await server.serve_forever()


async def _handle_toggle(body: str, devices: dict, execute, refresh_state) -> None:
    fields = parse_qs(body)
    serial = fields.get("serial", [None])[0]
    zone_number = int(fields.get("zone", [0])[0] or 0)
    device = devices.get(serial)
    if device is None:
        return
    zone = next((z for z in device.zones if z.number == zone_number), None)
    if zone is None or not zone.enabled:
        return
    await execute(ApplyZoneState(serial=serial, zone=zone_number, on=zone.state != "on"))
    await refresh_state(serial)


def _status_page(connected: bool, devices: dict) -> bytes:
    cards = "".join(_device_card(device) for device in devices.values())
    body = cards if cards else "<p class='empty'>No devices discovered yet.</p>"
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="{POLL_STATE_SECONDS}">
<title>Audioflow2MQTT</title>
<style>
  :root{{--bg:#f5f5f7;--fg:#1a1a1a;--card:#fff;--border:#e2e2e5;--muted:#888;--on:#2ecc71;--off:#e74c3c}}
  @media (prefers-color-scheme: dark){{
    :root{{--bg:#17181a;--fg:#eee;--card:#232427;--border:#34353a;--muted:#9a9a9e}}
  }}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    max-width:720px;margin:2rem auto;padding:0 1rem;color:var(--fg);background:var(--bg)}}
  h1{{font-size:1.4rem;margin-bottom:.25rem}}
  .badge{{display:inline-block;padding:.2rem .6rem;border-radius:.25rem;color:#fff;font-size:.85rem}}
  .empty{{color:var(--muted)}}
  .device{{background:var(--card);border:1px solid var(--border);border-radius:.6rem;margin-top:1.2rem;overflow:hidden}}
  .device-header{{display:flex;align-items:center;gap:.7rem;padding:.7rem 1rem;border-bottom:1px solid var(--border)}}
  .device-header strong{{font-size:1.05rem}}
  .device-header small{{color:var(--muted)}}
  .device-header .text{{display:flex;flex-wrap:wrap;align-items:baseline;gap:.5rem;flex:1}}
  .device-photo{{width:2.6rem;height:2.6rem;object-fit:contain;border-radius:.35rem;background:var(--bg);flex:none}}
  .zone{{display:flex;align-items:center;gap:.6rem;padding:.55rem 1rem;border-bottom:1px solid var(--border)}}
  .zone:last-child{{border-bottom:none}}
  .dot{{width:.55rem;height:.55rem;border-radius:50%;background:var(--muted);flex:none}}
  .dot.on{{background:var(--on)}}
  .zone-name{{flex:1}}
  .zone-name small{{color:var(--muted)}}
  form{{margin:0}}
  .switch{{position:relative;display:inline-block;width:2.6rem;height:1.5rem;flex:none}}
  .switch input{{opacity:0;width:0;height:0}}
  .slider{{position:absolute;inset:0;background:var(--border);border-radius:1.5rem;transition:.15s;cursor:pointer}}
  .slider::before{{content:"";position:absolute;width:1.1rem;height:1.1rem;left:.2rem;bottom:.2rem;background:#fff;border-radius:50%;transition:.15s}}
  input:checked + .slider{{background:var(--on)}}
  input:checked + .slider::before{{transform:translateX(1.1rem)}}
  input:disabled + .slider{{opacity:.4;cursor:not-allowed}}
</style>
</head><body>
<h1>Audioflow2MQTT</h1>
<span class="badge" style="background:{'var(--on)' if connected else 'var(--off)'}">MQTT {'Connected' if connected else 'Disconnected'}</span>
{body}
</body></html>"""
    return html.encode()


def _device_card(device) -> str:
    zones = "".join(_zone_row(device.info.serial, zone) for zone in device.zones)
    status_colour = "var(--on)" if device.health.online else "var(--off)"
    status_text = "online" if device.health.online else "offline"
    photo_url = MODEL_PHOTOS.get(len(device.zones))
    photo = f"<img class='device-photo' src='{photo_url}' alt=''>" if photo_url else ""
    return (
        "<div class='device'>"
        f"<div class='device-header'>{photo}<div class='text'><strong>{device.info.name}</strong>"
        f"<small>{device.info.model} · {device.info.serial}</small></div>"
        f"<span style='color:{status_colour}'>{status_text}</span></div>"
        f"{zones}</div>"
    )


def _zone_row(serial: str, zone) -> str:
    disabled_note = "" if zone.enabled else " <small>(disabled)</small>"
    return (
        "<div class='zone'>"
        f"<span class='dot {'on' if zone.state == 'on' else ''}'></span>"
        f"<span class='zone-name'>{zone.name}{disabled_note}</span>"
        f"<form method='post' action='toggle'>"
        f"<input type='hidden' name='serial' value='{serial}'>"
        f"<input type='hidden' name='zone' value='{zone.number}'>"
        f"<label class='switch'><input type='checkbox' onchange='this.form.submit()' "
        f"{'checked' if zone.state == 'on' else ''} {'disabled' if not zone.enabled else ''}>"
        f"<span class='slider'></span></label></form>"
        "</div>"
    )


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
            asyncio.create_task(_health_server(transport, devices, orchestrator.execute, orchestrator.refresh_state)),
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
