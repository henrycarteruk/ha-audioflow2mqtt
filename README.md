# Audioflow2MQTT

This is the Home Assistant **add-on** version of [Audioflow2MQTT](https://github.com/henrycarteruk/audioflow2mqtt). It enables local control of your Audioflow speaker switch(es) via MQTT and supports Home Assistant MQTT discovery for easy integration. It can automatically discover the Audioflow devices on your network via UDP discovery, or you can specify their IP addresses if you'd rather not use discovery.

<br>

# Adding to Home Assistant
1. Open your Home Assistant dashboard.
2. Navigate to **Settings → Apps**.
3. Click the **Install App** button in the bottom-right.
4. Click the three dots menu in the top-right corner and select **Repositories**.
5. Click the **+ App** button in the bottom-right.
6. Paste **https://github.com/henrycarteruk/ha-audioflow2mqtt** into the text field.
7. Click **Add** and close the pop-up. Refresh the page; the add-on should now be visible.
8. Install the add-on. The first install builds the image locally on your Home Assistant host, which can take a few minutes (longer on a Raspberry Pi). Then configure and start it.

<br>

# Supported architectures
The add-on is built locally on installation for the following architectures:

| Architecture | Examples |
|--------------|----------|
| `amd64` | Intel/AMD x86-64 (NUC, generic server, most VMs) |
| `aarch64` | 64-bit ARM (Home Assistant Green & Yellow, Raspberry Pi 3/4/5 on a 64-bit OS) |
| `armv7` | 32-bit ARMv7 (Raspberry Pi 2/3 on a 32-bit OS) |

`armhf` (ARMv6 — Raspberry Pi 1 and Pi Zero) is **not** supported.

<br>

# Configuration

The add-on is configured from the **Configuration** tab in Home Assistant.

| Option | Default | Description |
|--------|---------|-------------|
| `mqtt_host` | _(empty)_ | IP address or hostname of the MQTT broker. **Leave empty** to use the broker provided by the Home Assistant Supervisor. |
| `mqtt_port` | `1883` | The port the MQTT broker is bound to. Ignored when the Supervisor broker is used. |
| `mqtt_user` | _(empty)_ | Username for the MQTT broker. |
| `mqtt_pass` | _(empty)_ | Password for the MQTT broker. |
| `qos` | `1` | MQTT Quality of Service level (`0`–`2`) for published messages. |
| `base_topic` | `audioflow2mqtt` | The topic prefix to use for all payloads. |
| `devices` | _(empty)_ | IP address(es) of your Audioflow device(s). Leave empty to find them automatically via UDP discovery; set them to skip discovery. |
| `log_level` | `info` | Minimum log level. One of `debug`, `info`, `warning`, `error`. |

When `mqtt_host` is left empty, broker host, port, username and password are taken automatically from the Supervisor's MQTT service. Home Assistant MQTT discovery is always enabled.

<br>

# Home Assistant
The add-on uses Home Assistant MQTT discovery to create a Device for each Audioflow switch with:
- Switch entities for each zone
- Button entities to turn all zones on and off
- Sensors for SSID, RSSI (signal strength), and Wi-Fi channel

![Home Assistant Device screenshot](ha_screenshot.png)

<br>

# MQTT topic structure

All topics are prefixed with your `base_topic` (default `audioflow2mqtt`). The examples below use the default base topic and the serial number `0123456789` (found on the sticker on the bottom of the device). Zones are numbered A = 1, B = 2, and so on.

## Commands you send

Publish to these topics to control the gateway and devices. Per-zone commands take a trailing zone number; the others don't.

| Command topic | Payload | Effect |
|---------------|---------|--------|
| `audioflow2mqtt/0123456789/set_zone_state/<zone>` | `on`, `off`, `toggle` | Turn one zone on/off, or toggle it |
| `audioflow2mqtt/0123456789/set_zone_state` | `on`, `off` | Turn **all** zones on/off (no zone number; `toggle` isn't supported here) |
| `audioflow2mqtt/0123456789/set_zone_enable/<zone>` | `1`, `0` | Enable (`1`) or disable (`0`) one zone |
| `audioflow2mqtt/discover` | _(any)_ | Trigger a fresh UDP discovery sweep to pick up newly added devices |

## Topics the gateway publishes

**Zone state**, published after any change and on each poll:

- `audioflow2mqtt/0123456789/zone_state/<zone>`: `on` or `off`
- `audioflow2mqtt/0123456789/zone_enabled/<zone>`: `1` or `0`

> The device doesn't report a new state after a command, so the gateway re-reads the affected zone(s) and republishes.

**Network info**, polled periodically:

- `audioflow2mqtt/0123456789/network_info/ssid`
- `audioflow2mqtt/0123456789/network_info/channel`
- `audioflow2mqtt/0123456789/network_info/rssi`

**Availability**, retained for Home Assistant and monitoring:

- `audioflow2mqtt/status`: `online`/`offline` for the gateway itself; if the gateway disconnects unexpectedly, the broker publishes `offline` on its behalf
- `audioflow2mqtt/0123456789/status`: `online`/`offline` for an individual device

<br>

# Notes
A single instance handles multiple Audioflow devices — every topic is namespaced by the device serial number, so they don't collide.

For reliability, give each Audioflow device a static IP (e.g. a DHCP reservation) and set `devices` rather than relying on UDP discovery. UDP discovery only works when the device is on the same subnet as the machine running Home Assistant.

<br>

# License

Licensed under the [GNU GPLv3](LICENSE).

This is a modified fork of the original [audioflow2mqtt](https://github.com/tediore/audioflow2mqtt) by [tediore](https://github.com/tediore). Original work © [tediore](https://github.com/tediore); modifications © [henrycarteruk](https://github.com/henrycarteruk). As a derivative of a GPLv3 project, it remains under GPLv3.

If you find it useful, consider buying the original author a coffee to support their work:

<a href="https://www.buymeacoffee.com/tediore" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>
