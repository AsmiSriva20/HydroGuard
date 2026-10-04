import time

from app.models.payloads import SensorPayload, derive_condition_status, expected_alert_value
from app.models.sensor import SensorLog


async def store_log(payload: SensorPayload, threshold_sec: int) -> SensorLog:
    condition_status = derive_condition_status(payload, threshold_sec)
    alert_value = expected_alert_value(condition_status)

    from app.core.config import get_settings
    from app.services.analytics_service import usage_segments

    previous = await SensorLog.find_one(
        SensorLog.device_id == payload.device_id, sort=[("timestamp", -1)]
    )
    log = SensorLog(
        usage_segments=usage_segments(
            previous, payload.timestamp, get_settings().device_offline_after_sec
        ),
        incident=condition_status.value in {"WARNING", "WASTAGE_ALERT", "LEAK", "CRITICAL"}
        and (
            previous is None
            or previous.status != condition_status.value
            or payload.timestamp - previous.timestamp > get_settings().device_offline_after_sec
        ),
        device_id=payload.device_id,
        timestamp=payload.timestamp,
        water_flow=payload.water_flow,
        human_present=payload.human_present,
        water_detected=payload.water_detected,
        alert=alert_value,
        status=condition_status.value,
        running_duration_sec=payload.running_duration_sec,
        flow_rate_lpm=payload.flow_rate_lpm,
        created_at=int(time.time()),
    )

    await log.insert()
    return log


async def get_history(
    device_id: str,
    start_time: int | None = None,
    end_time: int | None = None,
    limit: int = 100,
) -> list[SensorLog]:
    query = SensorLog.find(SensorLog.device_id == device_id)

    if start_time is not None:
        query = query.find(SensorLog.timestamp >= start_time)

    if end_time is not None:
        query = query.find(SensorLog.timestamp <= end_time)

    return await query.sort(-SensorLog.timestamp).limit(limit).to_list()
