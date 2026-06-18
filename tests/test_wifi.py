from audioflow2mqtt.wifi import parse_wifi, WifiInfo


def test_multi_word_ssid_is_preserved_and_trimmed():
    info = parse_wifi("My Home Net [11] (-70 dBm)")
    assert info.ssid == "My Home Net"
    assert info.channel == 11
    assert info.rssi == -70


def test_tolerates_extra_whitespace():
    info = parse_wifi("Net [ 6 ]  ( -58  dBm )")
    assert info == WifiInfo(ssid="Net", channel=6, rssi=-58)


def test_malformed_string_returns_none():
    assert parse_wifi("not a wifi string") is None
    assert parse_wifi("SSID [6]") is None          # missing rssi
    assert parse_wifi("SSID (-58 dBm)") is None     # missing channel


def test_empty_or_none_input_returns_none():
    assert parse_wifi("") is None
    assert parse_wifi(None) is None
    assert parse_wifi("   ") is None


def test_parses_well_formed_wifi_string():
    info = parse_wifi("HomeNet [6] (-58 dBm)")
    assert info == WifiInfo(ssid="HomeNet", channel=6, rssi=-58)
