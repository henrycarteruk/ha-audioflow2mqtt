"""Fake Audioflow device for local testing, without real hardware.

Serves the same HTTP API as a real device (/switch, /zones, /zonename/<n>,
/reboot_now) and answers UDP discovery pings, so audioflow2mqtt can discover,
poll, and control it exactly as it would a real switch. Point the add-on at
it with `ip:port` in the `devices` option (e.g. "127.0.0.1:8000") — no code
changes needed, httpx treats the port as part of the host.

Run: uv run python tools/fake_device.py [options]
Self-check: uv run python tools/fake_device.py --selftest
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DISCOVERY_PORT = 10499
PING = b"afping"


class DeviceState:
    def __init__(self, serial: str, model: str, name: str, wifi: str, zone_count: int):
        self.serial = serial
        self.model = model
        self.name = name
        self.version = "1.0.0-fake"
        self.wifi = wifi
        self.lock = threading.Lock()
        self.zones = [
            {"name": f"Zone {i}", "state": "off", "enabled": 1} for i in range(1, zone_count + 1)
        ]


class Handler(BaseHTTPRequestHandler):
    # httpx keeps connections alive by default; HTTP/1.0 (the base class default)
    # closes after one response, which httpx reads as a mid-request connection drop.
    protocol_version = "HTTP/1.1"
    server: ThreadingHTTPServer  # .state is set by run()/_selftest(), duck-typed

    def _json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _empty(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler naming)
        state = self.server.state
        if self.path == "/switch":
            self._json(200, {
                "serial": state.serial,
                "model": state.model,
                "name": state.name,
                "version": state.version,
                "wifi": state.wifi,
            })
        elif self.path == "/zones":
            with state.lock:
                self._json(200, {"zones": list(state.zones)})
        elif self.path == "/reboot_now":
            self._empty(200)
        else:
            self._empty(404)

    def do_PUT(self):  # noqa: N802
        state = self.server.state
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        if self.path == "/zones":
            with state.lock:
                for zone, value in zip(state.zones, body.split(" ")):
                    zone["state"] = "on" if value == "1" else "off"
            self._empty(200)
        elif self.path.startswith("/zones/"):
            number = int(self.path.removeprefix("/zones/"))
            with state.lock:
                state.zones[number - 1]["state"] = "on" if body == "1" else "off"
            self._empty(200)
        elif self.path.startswith("/zonename/"):
            number = int(self.path.removeprefix("/zonename/"))
            enabled, name = body[0], body[1:]
            with state.lock:
                state.zones[number - 1]["enabled"] = int(enabled)
                state.zones[number - 1]["name"] = name
            self._empty(200)
        else:
            self._empty(404)


def _discovery_responder() -> None:
    # ponytail: daemon thread, no shutdown plumbing — dies with the process
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", DISCOVERY_PORT))
    print(f"[fake_device] answering UDP discovery on :{DISCOVERY_PORT}")
    while True:
        data, addr = sock.recvfrom(1024)
        if data == PING:
            sock.sendto(PING, addr)


def run(args) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    server.state = DeviceState(args.serial, args.model, args.name, args.wifi, args.zones)
    threading.Thread(target=_discovery_responder, daemon=True).start()
    print(f"[fake_device] {args.name} ({args.serial}) serving on :{args.port}, {args.zones} zones")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def _selftest() -> None:
    """Exercise every endpoint against a real server on an ephemeral port."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.state = DeviceState("SELFTEST", "AF1", "Test", "FakeNet [6] (-50 dBm)", 2)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    def get(path):
        with urllib.request.urlopen(base + path) as r:
            return r.status, r.read()

    def put(path, body):
        req = urllib.request.Request(base + path, data=body.encode(), method="PUT")
        with urllib.request.urlopen(req) as r:
            return r.status

    status, body = get("/switch")
    assert status == 200 and json.loads(body)["serial"] == "SELFTEST"

    status, body = get("/zones")
    zones = json.loads(body)["zones"]
    assert len(zones) == 2 and zones[0]["state"] == "off"

    assert put("/zones/1", "1") == 200
    assert json.loads(get("/zones")[1])["zones"][0]["state"] == "on"

    assert put("/zones", "0 1") == 200
    zones = json.loads(get("/zones")[1])["zones"]
    assert zones[0]["state"] == "off" and zones[1]["state"] == "on"

    assert put("/zonename/1", "0Kitchen") == 200
    zones = json.loads(get("/zones")[1])["zones"]
    assert zones[0]["enabled"] == 0 and zones[0]["name"] == "Kitchen"

    assert get("/reboot_now")[0] == 200

    server.shutdown()
    print("selftest OK")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--serial", default="FAKE0001")
    parser.add_argument("--model", default="AF1")
    parser.add_argument("--name", default="Fake Switch")
    parser.add_argument("--wifi", default="FakeNet [6] (-50 dBm)")
    parser.add_argument("--zones", type=int, default=4)
    parser.add_argument("--selftest", action="store_true", help="Run a self-check and exit")
    args = parser.parse_args()

    if args.selftest:
        _selftest()
        return

    run(args)


if __name__ == "__main__":
    sys.exit(main())
