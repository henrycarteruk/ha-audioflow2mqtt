# 0003 — Read Supervisor MQTT config via the REST API, not bashio

Home Assistant add-ons conventionally read injected services (like the MQTT broker)
using **bashio** (`bashio::services mqtt host`) from a shell run-script, which requires
basing the image on the HA base image and adding a shell layer.

We instead call the **Supervisor REST API** directly from Python —
`GET http://supervisor/services/mqtt` with `Authorization: Bearer ${SUPERVISOR_TOKEN}`
— using the httpx client we already depend on. `config.yaml` declares
`hassio_api: true` and `services: ["mqtt:need"]`. Explicit `mqtt_host`/`mqtt_port`
options override the discovered values.

This keeps the entire add-on in one language on a slim `python:3-alpine` base with no
bashio/shell indirection. Recorded because bashio is the idiomatic default; without
this note someone would likely "fix" the absence of bashio by reintroducing it.
