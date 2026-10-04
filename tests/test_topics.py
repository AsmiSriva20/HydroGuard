from app.mqtt.topics import device_id_from_topic, topic_kind


class TestTopicKind:
    def test_sensor(self):
        assert topic_kind("home/bathroom/device01/sensor") == "sensor"

    def test_alert(self):
        assert topic_kind("home/bathroom/device01/alert") == "alert"

    def test_status(self):
        assert topic_kind("home/bathroom/device01/status") == "status"

    def test_unknown(self):
        assert topic_kind("home/bathroom/device01/other") is None


class TestDeviceIdFromTopic:
    def test_extracts_device_id(self):
        assert device_id_from_topic("home/bathroom/device01/sensor") == "device01"

    def test_returns_none_for_short_topic(self):
        assert device_id_from_topic("home/sensor") is None
