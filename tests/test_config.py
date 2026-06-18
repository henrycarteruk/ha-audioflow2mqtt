import asyncio
import json

import httpx

from audioflow2mqtt.config import resolve_config, Config, load_options, fetch_mqtt_service


def test_load_options_reads_json(tmp_path):
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"base_topic": "x", "qos": 2}))
    assert load_options(str(path)) == {"base_topic": "x", "qos": 2}


def test_fetch_mqtt_service_returns_data():
    def handler(request):
        assert request.url.path == "/services/mqtt"
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(200, json={"result": "ok", "data": {"host": "core-mosquitto", "port": 1883}})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def go():
        try:
            return await fetch_mqtt_service(http, token="tok")
        finally:
            await http.aclose()

    assert asyncio.run(go()) == {"host": "core-mosquitto", "port": 1883}


def test_fetch_mqtt_service_returns_none_without_token():
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500)))

    async def go():
        try:
            return await fetch_mqtt_service(http, token=None)
        finally:
            await http.aclose()

    assert asyncio.run(go()) is None


def test_defaults_applied_for_omitted_options():
    cfg = resolve_config({})
    assert cfg.mqtt_port == 1883
    assert cfg.qos == 1
    assert cfg.base_topic == "audioflow2mqtt"
    assert cfg.log_level == "info"


def test_supervisor_service_fills_broker_fields():
    cfg = resolve_config(
        {},
        mqtt_service={
            "host": "core-mosquitto",
            "port": 1884,
            "username": "addons",
            "password": "secret",
        },
    )
    assert cfg.mqtt_host == "core-mosquitto"
    assert cfg.mqtt_port == 1884
    assert cfg.mqtt_user == "addons"
    assert cfg.mqtt_pass == "secret"


def test_explicit_options_override_supervisor_service():
    cfg = resolve_config(
        {"mqtt_host": "10.0.0.5", "mqtt_user": "me"},
        mqtt_service={
            "host": "core-mosquitto",
            "port": 1883,
            "username": "addons",
            "password": "secret",
        },
    )
    assert cfg.mqtt_host == "10.0.0.5"      # explicit wins
    assert cfg.mqtt_user == "me"            # explicit wins
    assert cfg.mqtt_pass == "secret"        # gap filled from service


def test_devices_list_is_cleaned_of_blanks():
    cfg = resolve_config({"devices": ["10.0.0.1", "", "10.0.0.2"]})
    assert cfg.devices == ["10.0.0.1", "10.0.0.2"]


def test_no_devices_signals_discovery():
    assert resolve_config({}).devices is None
    assert resolve_config({"devices": []}).devices is None
    assert resolve_config({"devices": ["", None]}).devices is None


def test_invalid_log_level_falls_back_to_info():
    assert resolve_config({"log_level": "banana"}).log_level == "info"


def test_log_level_is_normalized_lowercase():
    assert resolve_config({"log_level": "WARNING"}).log_level == "warning"


def test_no_host_anywhere_resolves_to_none():
    assert resolve_config({}, mqtt_service=None).mqtt_host is None
    assert resolve_config({"mqtt_host": ""}, mqtt_service={}).mqtt_host is None


def test_home_assistant_is_always_on():
    # Dropped as a configurable option; explicit false in options is ignored.
    assert resolve_config({}).home_assistant is True
    assert resolve_config({"home_assistant": False}).home_assistant is True


def test_explicit_broker_options_map_into_config():
    cfg = resolve_config(
        {"mqtt_host": "10.0.0.5", "mqtt_port": 1884, "base_topic": "speakers"}
    )
    assert cfg.mqtt_host == "10.0.0.5"
    assert cfg.mqtt_port == 1884
    assert cfg.base_topic == "speakers"
