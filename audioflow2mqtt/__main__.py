"""Entrypoint: build real dependencies and run the Orchestrator.

This module is intentionally thin glue — all decision logic lives in the
unit-tested modules (config, dispatch, app, mqtt, mqtt_transport, ...).
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

import httpx

from .app import Device, Orchestrator
from .config import Config, fetch_mqtt_service, load_options, resolve_config
from .device import AudioflowClient
from .discovery import discover_devices
from .mqtt_transport import MqttTransport

POLL_STATE_SECONDS = 10
POLL_NETWORK_SECONDS = 60


async def _acquire_devices(config: Config, http: httpx.AsyncClient) -> dict[str, Device]:
    ips = config.devices if config.devices else await discover_devices()
    devices: dict[str, Device] = {}
    for ip in ips:
        client = AudioflowClient(ip, http)
        info = await client.get_info()
        zones = await client.get_zones()
        devices[info.serial] = Device(client=client, info=info, zones=zones)
        logging.info("Found Audioflow %s (%s) at %s", info.name, info.serial, ip)
    return devices


async def _poll(orchestrator: Orchestrator, devices, interval: int, refresh) -> None:
    while True:
        await asyncio.sleep(interval)
        for serial in list(devices):
            await refresh(serial)


async def run() -> None:
    options = load_options()
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

        devices = await _acquire_devices(config, http)
        if not devices:
            logging.error("No Audioflow devices found; exiting.")
            sys.exit(1)

        transport = MqttTransport(config)
        orchestrator = Orchestrator(
            config, transport, devices, http=http, discover=discover_devices
        )

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, transport.stop)

        async def on_connect(_transport) -> None:
            await orchestrator.on_connect()
            for serial in list(devices):
                await orchestrator.refresh_state(serial)
                await orchestrator.refresh_network(serial)

        pollers = [
            asyncio.create_task(_poll(orchestrator, devices, POLL_STATE_SECONDS, orchestrator.refresh_state)),
            asyncio.create_task(_poll(orchestrator, devices, POLL_NETWORK_SECONDS, orchestrator.refresh_network)),
        ]
        try:
            await transport.run_forever(orchestrator.handle_message, on_connect=on_connect)
        finally:
            for poller in pollers:
                poller.cancel()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
