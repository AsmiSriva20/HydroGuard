import pytest
from pydantic import ValidationError

from app.models.payloads import (
    AlertPayload,
    AlertStrength,
    AlertType,
    ConditionStatus,
    DeviceStatusEnum,
    SensorPayload,
    StatusPayload,
    compute_strength,
    derive_condition_status,
)


class TestSensorPayload:
    def test_valid_minimum(self):
        p = SensorPayload(
            device_id="device01",
            timestamp=1778926532,
            water_flow=True,
            human_present=False,
            running_duration_sec=287,
        )

        assert p.flow_rate_lpm is None

    def test_valid_with_flow_rate(self):
        p = SensorPayload(
            device_id="device01",
            timestamp=1778926532,
            water_flow=True,
            human_present=False,
            running_duration_sec=0,
            flow_rate_lpm=4.7,
        )

        assert p.flow_rate_lpm == 4.7

    def test_rejects_bad_device_id(self):
        with pytest.raises(ValidationError):
            SensorPayload(
                device_id="bad id!",
                timestamp=1778926532,
                water_flow=True,
                human_present=False,
                running_duration_sec=0,
            )

    def test_rejects_negative_duration(self):
        with pytest.raises(ValidationError):
            SensorPayload(
                device_id="device01",
                timestamp=1778926532,
                water_flow=True,
                human_present=False,
                running_duration_sec=-1,
            )

    def test_rejects_string_boolean(self):
        with pytest.raises(ValidationError):
            SensorPayload(
                device_id="device01",
                timestamp=1778926532,
                water_flow="true",
                human_present=False,
                running_duration_sec=0,
            )


class TestConditionStatus:
    def test_normal(self):
        payload = SensorPayload(
            device_id="device01",
            timestamp=1778926532,
            water_flow=0,
            human_present=0,
            water_detected=0,
            running_duration_sec=0,
        )

        assert derive_condition_status(payload, 300) == ConditionStatus.NORMAL

    def test_normal_flow(self):
        payload = SensorPayload(
            device_id="device01",
            timestamp=1778926532,
            water_flow=1,
            human_present=1,
            water_detected=0,
            running_duration_sec=0,
        )

        assert derive_condition_status(payload, 300) == ConditionStatus.NORMAL_FLOW

    def test_warning(self):
        payload = SensorPayload(
            device_id="device01",
            timestamp=1778926532,
            water_flow=1,
            human_present=0,
            water_detected=0,
            running_duration_sec=299,
        )

        assert derive_condition_status(payload, 300) == ConditionStatus.WARNING

    def test_alert(self):
        payload = SensorPayload(
            device_id="device01",
            timestamp=1778926532,
            water_flow=1,
            human_present=0,
            water_detected=0,
            running_duration_sec=300,
        )

        assert derive_condition_status(payload, 300) == ConditionStatus.ALERT

    def test_fc37_only_is_leak_not_critical(self):
        payload = SensorPayload(
            device_id="device01",
            timestamp=1778926532,
            water_flow=0,
            human_present=0,
            water_detected=1,
            running_duration_sec=0,
        )

        assert derive_condition_status(payload, 300) == ConditionStatus.LEAK

    def test_flow_and_fc37_is_critical(self):
        payload = SensorPayload(
            device_id="device01",
            timestamp=1778926532,
            water_flow=1,
            human_present=0,
            water_detected=1,
            running_duration_sec=0,
        )

        assert derive_condition_status(payload, 300) == ConditionStatus.CRITICAL


class TestAlertPayload:
    def test_valid(self):
        a = AlertPayload(
            device_id="device01",
            timestamp=1778926833,
            alert_type=AlertType.WATER_RUNNING_NO_HUMAN,
            duration_sec=301,
            strength=AlertStrength.HIGH,
        )

        assert a.alert_type == AlertType.WATER_RUNNING_NO_HUMAN

    def test_allows_zero_duration_for_immediate_critical(self):
        a = AlertPayload(
            device_id="device01",
            timestamp=1778926833,
            alert_type=AlertType.CRITICAL,
            duration_sec=0,
            strength=AlertStrength.HIGH,
        )

        assert a.alert_type == AlertType.CRITICAL

    def test_rejects_unknown_alert_type(self):
        with pytest.raises(ValidationError):
            AlertPayload(
                device_id="device01",
                timestamp=1778926833,
                alert_type="UNKNOWN_TYPE",
                duration_sec=301,
                strength=AlertStrength.LOW,
            )


class TestStatusPayload:
    def test_online(self):
        s = StatusPayload(
            device_id="device01",
            timestamp=1778926532,
            status=DeviceStatusEnum.ONLINE,
            uptime_sec=15420,
        )

        assert s.status == DeviceStatusEnum.ONLINE

    def test_rssi_must_be_non_positive(self):
        with pytest.raises(ValidationError):
            StatusPayload(
                device_id="device01",
                timestamp=1778926532,
                status=DeviceStatusEnum.ONLINE,
                uptime_sec=10,
                rssi=5,
            )


class TestComputeStrength:
    @pytest.mark.parametrize(
        "duration, expected",
        [
            (0, AlertStrength.LOW),
            (300, AlertStrength.LOW),
            (599, AlertStrength.LOW),
            (600, AlertStrength.MEDIUM),
            (1199, AlertStrength.MEDIUM),
            (1200, AlertStrength.HIGH),
            (9999, AlertStrength.HIGH),
        ],
    )
    def test_bucketing(self, duration, expected):
        assert compute_strength(duration) == expected
