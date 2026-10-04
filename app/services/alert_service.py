import time

from app.core.config import Settings
from app.models.alert import Alert
from app.models.device import Device
from app.models.payloads import (
    AlertPayload,
    ConditionStatus,
    SensorPayload,
    derive_condition_status,
    should_notify_user,
)
from app.services import notification_service
from app.services.websocket_manager import ws_manager

SEVERITIES = {
    "WARNING": "WARNING",
    "WASTAGE_ALERT": "HIGH",
    "LEAK": "HIGH",
    "CRITICAL": "CRITICAL",
    "OFFLINE": "WARNING",
}
RANK = {"INFO": 0, "WARNING": 1, "HIGH": 2, "CRITICAL": 3}
MESSAGES = {
    "WARNING": "Water is flowing without human presence.",
    "WASTAGE_ALERT": "Unattended water flow exceeded the configured threshold.",
    "LEAK": "Water contact detected without substantial flow.",
    "CRITICAL": "Leak detected with substantial water flow.",
    "OFFLINE": "Device telemetry has stopped.",
}


def is_abnormal(payload: SensorPayload, threshold_sec: int) -> bool:
    return should_notify_user(derive_condition_status(payload, threshold_sec))


def has_reset(payload: SensorPayload, threshold_sec: int) -> bool:
    return not is_abnormal(payload, threshold_sec)


def cooldown_allows(
    state: str, active_state: str | None, sent_at: dict[str, int], now: int, cooldown: int
) -> bool:
    escalation = RANK[SEVERITIES[state]] > RANK[SEVERITIES.get(active_state, "INFO")]
    return escalation or state not in sent_at or now - sent_at[state] >= cooldown


def serialize_alert(alert: Alert) -> dict:
    return {
        "alert_id": alert.alert_id,
        "device_id": alert.device_id,
        "alert_type": alert.alert_type,
        "status": alert.alert_type,
        "severity": alert.severity,
        "strength": alert.strength,
        "message": alert.message,
        "timestamp": alert.timestamp,
        "duration_sec": alert.duration_sec,
        "acknowledged": alert.acknowledged,
        "resolved": alert.resolved,
        "notified": int(alert.notified),
    }


async def resolve_alerts(device_id: str, keep: str | None = None) -> None:
    query = {"device_id": device_id, "resolved": False}
    if keep:
        query["alert_type"] = {"$ne": keep}
    alerts = await Alert.find(query).to_list()
    for alert in alerts:
        alert.resolved = True
        await alert.save()
        await ws_manager.broadcast(
            device_id, {"event": "ALERT_RESOLVED", "data": serialize_alert(alert)}
        )


async def evaluate_state(
    device: Device,
    state: str,
    timestamp: int,
    duration: int,
    settings: Settings,
    send_notification: bool = True,
) -> Alert | None:
    previous = device.active_alert_status
    await resolve_alerts(device.device_id, keep=state)
    if state not in SEVERITIES:
        device.active_alert_at = None
        device.active_alert_status = None
        await device.save()
        return None
    # One database record per active episode; cooldown governs notification repeats.
    active = await Alert.find_one(
        {"device_id": device.device_id, "alert_type": state, "resolved": False}
    )
    created = active is None
    alert = active or Alert(
        device_id=device.device_id,
        alert_type=state,
        severity=SEVERITIES[state],
        strength=SEVERITIES[state],
        message=MESSAGES[state],
        timestamp=timestamp,
        duration_sec=duration,
        created_at=int(time.time()),
    )
    if created:
        await alert.insert()
    now = int(time.time())
    if send_notification and cooldown_allows(
        state, previous, device.alert_sent_at, now, settings.alert_cooldown_sec
    ):
        # Record attempts as well as successes to avoid flooding a failing provider.
        device.alert_sent_at[state] = now
        alert.notified = (
            await notification_service.send_alert_notification(alert, settings) or alert.notified
        )
        await alert.save()
    device.active_alert_at = alert.timestamp
    device.active_alert_status = state
    await device.save()
    if created:
        await ws_manager.broadcast(
            device.device_id, {"event": "alert_created", "data": serialize_alert(alert)}
        )
    if (
        state == "CRITICAL"
        and previous != "CRITICAL"
        and settings.automatic_shutoff_enabled
        and send_notification
    ):
        from app.mqtt.commands import close_valve

        await close_valve(device.device_id, settings)
    return alert if created else None


async def evaluate_sensor(
    payload: SensorPayload, device: Device, settings: Settings, send_notification: bool = True
) -> Alert | None:
    state = derive_condition_status(payload, settings.alert_duration_threshold_sec).value
    return await evaluate_state(
        device, state, payload.timestamp, payload.running_duration_sec, settings, send_notification
    )


async def ingest_alert_topic(
    payload: AlertPayload, device: Device, settings: Settings
) -> Alert | None:
    state = (
        ConditionStatus.CRITICAL.value
        if payload.alert_type.value == "CRITICAL"
        else ConditionStatus.WASTAGE_ALERT.value
    )
    return await evaluate_state(device, state, payload.timestamp, payload.duration_sec, settings)


async def list_alerts(
    device_id: str | None = None,
    start_time: int | None = None,
    end_time: int | None = None,
    limit: int = 100,
) -> list[Alert]:
    query = Alert.find()
    if device_id is not None:
        query = query.find(Alert.device_id == device_id)
    if start_time is not None:
        query = query.find(Alert.timestamp >= start_time)
    if end_time is not None:
        query = query.find(Alert.timestamp <= end_time)
    return await query.sort(-Alert.timestamp).limit(limit).to_list()
