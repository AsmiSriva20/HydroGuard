"""Deterministic sensor rules, shared by MQTT, REST and simulator."""

from app.models.payloads import ConditionStatus, SensorPayload


def derive_condition_status(
    payload: SensorPayload,
    threshold_sec: int,
    critical_flow_rate_lpm: float = 0.3,
) -> ConditionStatus:
    if (
        payload.water_detected == 1
        and payload.water_flow == 1
        and (payload.flow_rate_lpm is None or payload.flow_rate_lpm >= critical_flow_rate_lpm)
    ):
        return ConditionStatus.CRITICAL

    if payload.water_detected == 1:
        return ConditionStatus.LEAK

    if (
        payload.water_flow == 1
        and payload.human_present == 0
        and payload.running_duration_sec >= threshold_sec
    ):
        return ConditionStatus.ALERT

    if payload.water_flow == 1 and payload.human_present == 0:
        return ConditionStatus.WARNING

    if payload.water_flow == 1 and payload.human_present == 1:
        return ConditionStatus.NORMAL_FLOW

    return ConditionStatus.NORMAL
