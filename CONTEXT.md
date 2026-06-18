# audioflow2mqtt

A Home Assistant add-on that bridges Audioflow speaker switches to MQTT, exposing
their zones and network info as Home Assistant entities via MQTT discovery.

## Language

**Device**:
A physical Audioflow speaker switch, identified by its serial number. Exposes an
HTTP API (`/switch`, `/zones`, `/zonename/{n}`) that the gateway polls and commands.
_Avoid_: switch (reserved for the `/switch` HTTP endpoint), unit, box.

**Zone**:
One switchable speaker output on a device (zone A = 1, zone B = 2, …). Has a name,
a state (on/off), and an enabled flag. Zone names are stored in `zone_names`.
_Avoid_: switch, channel, output (in code/docs).

**Gateway**:
This add-on, acting as an MQTT participant. Owns gateway-scoped MQTT topics (e.g.
`BASE_TOPIC/discover`, `BASE_TOPIC/status`) and is represented in Home Assistant as
its own device (currently exposing the on-demand discovery button).
_Avoid_: bridge, daemon, service.

**Discovery**:
Two distinct things — disambiguate:
- _Device discovery_: finding Audioflow devices on the LAN via UDP broadcast.
- _MQTT discovery_ (a.k.a. _HA discovery_): publishing Home Assistant
  auto-configuration payloads so entities appear automatically.
_Avoid_: "discovery" unqualified.
