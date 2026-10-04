"""Serialize ingestion per device and share the MQTT and REST processing path."""

import asyncio
from collections import defaultdict

from app.core.config import Settings
from app.models.payloads import SensorPayload
from app.services import alert_service, device_service, sensor_service
from app.services.websocket_manager import ws_manager

_locks = defaultdict(asyncio.Lock)


async def ingest(
    payload: SensorPayload,
    settings: Settings,
    time_scale: int = 1,
    send_notification: bool = True,
    location: str | None = None,
):
    async with _locks[payload.device_id]:
        device = await device_service.touch_from_sensor(
            payload, settings.alert_duration_threshold_sec, time_scale
        )
        if location and not device.location:
            device.location = location.replace("_", " ")
            device.device_name = device.device_name or location.replace("_", " ").title()
            await device.save()
        await sensor_service.store_log(payload, settings.alert_duration_threshold_sec)
        alert = await alert_service.evaluate_sensor(payload, device, settings, send_notification)
        await ws_manager.broadcast(
            payload.device_id,
            {
                "event": "sensor_update",
                "data": {
                    **payload.model_dump(),
                    "status": device.condition_status,
                    "alert": device.alert,
                    "connection_status": device.status,
                    "last_seen": device.last_seen,
                },
            },
        )
        return device, alert
