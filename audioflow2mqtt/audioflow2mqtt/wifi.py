"""Pure parsing of an Audioflow device's `wifi` field into structured info.

The device reports Wi-Fi as a single string like ``SSID [channel] (rssi dBm)``.
This module turns it into a typed WifiInfo, returning None on malformed input
rather than producing garbage.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class WifiInfo:
    ssid: str
    channel: int
    rssi: int


def parse_wifi(raw: str | None) -> WifiInfo | None:
    match = re.match(r"^(.*)\[\s*(\d+)\s*\].*\(\s*(-?\d+)\s*dBm\s*\)", raw or "")
    if not match:
        return None
    ssid, channel, rssi = match.group(1), match.group(2), match.group(3)
    return WifiInfo(ssid=ssid.strip(), channel=int(channel), rssi=int(rssi))
