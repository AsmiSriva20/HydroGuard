from app.models.payloads import ConditionStatus, SensorPayload, derive_condition_status
from app.services.alert_service import has_reset, is_abnormal


def _payload(
    water: bool,
    human: bool,
    duration: int,
    water_detected: bool = False,
) -> SensorPayload:
    return SensorPayload(
        device_id="device01",
        timestamp=1778926532,
        water_flow=water,
        human_present=human,
        water_detected=water_detected,
        running_duration_sec=duration,
    )


class TestCombinedSensorValidation:
    def test_fc37_only_is_local_leak_not_critical(self):
        payload = _payload(False, False, 0, water_detected=True)

        assert derive_condition_status(payload, 300) == ConditionStatus.LEAK
        assert is_abnormal(payload, 300)

    def test_flow_only_with_human_is_normal_flow_not_critical(self):
        payload = _payload(True, True, 0, water_detected=False)

        assert derive_condition_status(payload, 300) == ConditionStatus.NORMAL_FLOW
        assert not is_abnormal(payload, 300)

    def test_flow_only_without_human_below_threshold_is_warning(self):
        payload = _payload(True, False, 299, water_detected=False)

        assert derive_condition_status(payload, 300) == ConditionStatus.WARNING
        assert is_abnormal(payload, 300)

    def test_flow_only_without_human_at_threshold_is_alert(self):
        payload = _payload(True, False, 300, water_detected=False)

        assert derive_condition_status(payload, 300) == ConditionStatus.ALERT
        assert is_abnormal(payload, 300)

    def test_flow_and_fc37_together_is_critical(self):
        payload = _payload(True, False, 0, water_detected=True)

        assert derive_condition_status(payload, 300) == ConditionStatus.CRITICAL
        assert is_abnormal(payload, 300)


class TestIsAbnormal:
    def test_below_threshold(self):
        assert is_abnormal(_payload(True, False, 299), 300)

    def test_at_threshold(self):
        assert is_abnormal(_payload(True, False, 300), 300)

    def test_above_threshold(self):
        assert is_abnormal(_payload(True, False, 600), 300)

    def test_water_off(self):
        assert not is_abnormal(_payload(False, False, 600), 300)

    def test_human_present(self):
        assert not is_abnormal(_payload(True, True, 600), 300)

    def test_fc37_only_is_abnormal_for_remote_notification(self):
        assert is_abnormal(_payload(False, False, 0, water_detected=True), 300)

    def test_flow_and_fc37_is_abnormal(self):
        assert is_abnormal(_payload(True, False, 0, water_detected=True), 300)


class TestHasReset:
    def test_water_off_resets(self):
        assert has_reset(_payload(False, False, 0), 300)

    def test_human_present_resets(self):
        assert has_reset(_payload(True, True, 0), 300)

    def test_fc37_only_keeps_remote_alert(self):
        assert not has_reset(_payload(False, False, 0, water_detected=True), 300)

    def test_abnormal_does_not_reset(self):
        assert not has_reset(_payload(True, False, 600), 300)

    def test_critical_does_not_reset(self):
        assert not has_reset(_payload(True, False, 0, water_detected=True), 300)
