import json
import logging
import time

from app.core.config import Settings
from app.models.payloads import (
    AlertPayload,
    SensorPayload,
    StatusPayload,
)
from app.mqtt.topics import device_id_from_topic, topic_kind
from app.services import alert_service, device_service, ingestion_service
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


def _validate_timestamp(timestamp: int, settings: Settings) -> bool:
    now = int(time.time())
    return (
        now - settings.timestamp_skew_past_sec
        <= timestamp
        <= now + settings.timestamp_skew_future_sec
    )


def _validate_topic_match(topic: str, device_id: str) -> bool:
    expected_device_id = device_id_from_topic(topic)
    return expected_device_id == device_id


async def handle_message(
    topic: str, raw: bytes, settings: Settings, retained: bool = False
) -> None:
    if len(raw) > settings.mqtt_max_payload_bytes:
        logger.warning("payload too large: topic=%s size=%d", topic, len(raw))
        return

    kind = topic_kind(topic)

    if kind is None:
        logger.debug("unknown topic, ignoring: %s", topic)
        return

    try:
        body = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        logger.warning("invalid JSON on %s: %s", topic, error)
        return

    try:
        if kind == "sensor":
            payload = SensorPayload.model_validate(body)

            if not _validate_topic_match(topic, payload.device_id):
                logger.warning("topic/device_id mismatch on %s: %s", topic, payload.device_id)
                return

            if not _validate_timestamp(payload.timestamp, settings):
                logger.warning("timestamp out of skew window: %s ts=%d", topic, payload.timestamp)
                return

            await _handle_sensor(payload, settings, topic.split("/")[1])

        elif kind == "alert":
            if retained:
                return
            alert_payload = AlertPayload.model_validate(body)

            if not _validate_topic_match(topic, alert_payload.device_id):
                logger.warning("topic/device_id mismatch on %s", topic)
                return

            if not _validate_timestamp(alert_payload.timestamp, settings):
                logger.warning("alert timestamp out of skew window: %s", topic)
                return

            async with ingestion_service._locks[alert_payload.device_id]:
                await _handle_alert(alert_payload, settings)

        elif kind == "status":
            status_payload = StatusPayload.model_validate(body)

            if not _validate_topic_match(topic, status_payload.device_id):
                logger.warning("topic/device_id mismatch on %s", topic)
                return

            if not _validate_timestamp(status_payload.timestamp, settings):
                logger.warning("status timestamp out of skew window: %s", topic)
                return

            if (
                retained
                and int(time.time()) - status_payload.timestamp >= settings.device_offline_after_sec
            ):
                logger.debug("ignoring stale retained heartbeat on %s", topic)
                return
            async with ingestion_service._locks[status_payload.device_id]:
                await _handle_status(status_payload, settings)

    except (ValueError, UnicodeDecodeError) as error:
        logger.warning("invalid telemetry on %s: %s", topic, error)


async def _handle_sensor(
    payload: SensorPayload, settings: Settings, location: str | None = None
) -> None:
    await ingestion_service.ingest(payload, settings, location=location)


async def _handle_alert(payload: AlertPayload, settings: Settings) -> None:
    device = await device_service._get_or_create(payload.device_id)
    await alert_service.ingest_alert_topic(payload, device, settings)


async def _handle_status(payload: StatusPayload, settings: Settings) -> None:
    device = await device_service.apply_status(payload)
    if device.status == "OFFLINE":
        await alert_service.evaluate_state(device, "OFFLINE", payload.timestamp, 0, settings)
    elif device.active_alert_status == "OFFLINE":
        await alert_service.resolve_alerts(device.device_id)
        device.active_alert_at = None
        device.active_alert_status = None
        await device.save()

    await ws_manager.broadcast(
        payload.device_id,
        {
            "event": "device_status",
            "data": {
                "device_id": payload.device_id,
                "status": payload.status.value,
                "uptime_sec": payload.uptime_sec,
                "timestamp": payload.timestamp,
            },
        },
    )
