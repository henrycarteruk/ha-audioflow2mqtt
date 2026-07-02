# Audioflow2MQTT

This is the Home Assistant **add-on** version of [Audioflow2MQTT](https://github.com/henrycarteruk/audioflow2mqtt). It enables local control of your Audioflow speaker switch(es) via MQTT and supports Home Assistant MQTT discovery for easy integration. It can automatically discover the Audioflow devices on your network via UDP discovery, or you can specify their IP addresses if you'd rather not use discovery.

The add-on uses Home Assistant MQTT discovery to create a Device for each Audioflow switch with:
- Switch entities for each zone
- Button entities to turn all zones on, turn all zones off, and reboot the device
- Sensors for SSID, RSSI (signal strength), and Wi-Fi channel

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

The add-on exposes a health endpoint on port 8099. The Supervisor monitors it and automatically restarts the add-on if MQTT connectivity is lost.
