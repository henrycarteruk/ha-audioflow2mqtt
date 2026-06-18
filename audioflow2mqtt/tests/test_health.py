from audioflow2mqtt.health import DeviceHealth


def test_single_failure_stays_online():
    health = DeviceHealth().failed()
    assert health.failures == 1
    assert health.online is True


def test_reaching_threshold_goes_offline():
    health = DeviceHealth().failed().failed()
    assert health.online is True       # 2 failures: still online
    health = health.failed()
    assert health.failures == 3
    assert health.online is False      # 3rd consecutive failure -> offline


def test_success_recovers_from_offline():
    offline = DeviceHealth().failed().failed().failed()
    assert offline.online is False
    recovered = offline.succeeded()
    assert recovered.failures == 0
    assert recovered.online is True


def test_fresh_health_is_online():
    health = DeviceHealth()
    assert health.online is True
    assert health.failures == 0
