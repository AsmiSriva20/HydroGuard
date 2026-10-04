import time

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from app.core.config import get_settings
from app.core.security import require_admin_api_key
from app.models.alert import Alert
from app.models.payloads import (
    DeviceRegisterRequest,
    SensorPayload,
    derive_condition_status,
    expected_alert_value,
)
from app.models.sensor import SensorLog
from app.services import (
    device_service,
    ingestion_service,
    sensor_service,
)
from app.services.websocket_manager import ws_manager

router = APIRouter(
    prefix="/api/devices",
    tags=["devices"],
)


def as01(value: int | bool | None) -> int:
    return 1 if value in (1, True) else 0


@router.get("")
async def list_devices() -> list[dict]:
    devices = await device_service.list_devices()

    return [
        {
            "device_id": device.device_id,
            "location": device.location,
            "device_name": device.device_name or device.device_id,
            "flow_rate_lpm": device.flow_rate_lpm,
            "connection_status": device.status,
            "status": device.condition_status,
            "last_seen": device.last_seen,
            "water_flow": as01(device.water_flow),
            "human_present": as01(device.human_present),
            "water_detected": as01(device.water_detected),
            "alert": as01(device.alert),
            "has_active_alert": as01(device.active_alert_at is not None),
        }
        for device in devices
    ]


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_api_key)],
)
async def register_device(
    req: DeviceRegisterRequest,
) -> dict:
    device = await device_service.register_device(req)

    return {
        "device_id": device.device_id,
        "location": device.location,
        "device_name": device.device_name or device.device_id,
        "flow_rate_lpm": device.flow_rate_lpm,
        "connection_status": device.status,
        "status": device.condition_status,
        "created_at": device.created_at,
    }


@router.get("/{device_id}/live")
async def get_live(
    device_id: str,
) -> dict:
    device = await device_service.get_device(device_id)

    if device is None:
        raise HTTPException(
            status_code=404,
            detail="device not found",
        )

    return {
        "device_id": device.device_id,
        "location": device.location,
        "device_name": device.device_name or device.device_id,
        "flow_rate_lpm": device.flow_rate_lpm,
        "connection_status": device.status,
        "status": device.condition_status,
        "water_flow": as01(device.water_flow),
        "human_present": as01(device.human_present),
        "water_detected": as01(device.water_detected),
        "alert": as01(device.alert),
        "running_duration_sec": (device.running_duration_sec or 0),
        "last_seen": device.last_seen,
        "uptime_sec": device.uptime_sec,
        "firmware_version": device.firmware_version,
        "has_active_alert": as01(device.active_alert_at is not None),
        "active_alert_status": device.active_alert_status,
    }


@router.get("/{device_id}/history")
async def get_history(
    device_id: str,
    start_time: int | None = Query(
        default=None,
        ge=0,
    ),
    end_time: int | None = Query(
        default=None,
        ge=0,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
    ),
) -> list[dict]:
    logs = await sensor_service.get_history(
        device_id,
        start_time,
        end_time,
        limit,
    )

    return [
        {
            "timestamp": log.timestamp,
            "water_flow": as01(log.water_flow),
            "human_present": as01(log.human_present),
            "water_detected": as01(log.water_detected),
            "alert": as01(log.alert),
            "status": log.status,
            "running_duration_sec": log.running_duration_sec,
            "flow_rate_lpm": log.flow_rate_lpm,
        }
        for log in logs
    ]


@router.post(
    "/{device_id}/simulate",
    dependencies=[Depends(require_admin_api_key)],
)
async def simulate_sensor(
    device_id: str,
    body: dict,
) -> dict:
    settings = get_settings()

    now = int(time.time())

    payload_data = {
        "device_id": device_id,
        "timestamp": now,
        "water_flow": 0,
        "human_present": 0,
        "water_detected": 0,
        "alert": 0,
        "running_duration_sec": 0,
        "flow_rate_lpm": 0,
        **body,
    }

    payload_data["device_id"] = device_id
    payload_data["timestamp"] = int(payload_data.get("timestamp") or now)

    try:
        payload = SensorPayload.model_validate(payload_data)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="invalid sensor payload") from error

    try:
        device, created_alert = await ingestion_service.ingest(
            payload, settings, time_scale=settings.demo_time_scale
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    condition_status = derive_condition_status(payload, settings.alert_duration_threshold_sec)
    alert_value = expected_alert_value(condition_status)

    return {
        "ok": 1,
        "device_id": device.device_id,
        "status": condition_status.value,
        "water_flow": payload.water_flow,
        "human_present": payload.human_present,
        "water_detected": payload.water_detected,
        "alert": alert_value,
        "running_duration_sec": (payload.running_duration_sec),
        "flow_rate_lpm": payload.flow_rate_lpm,
        "created_alert": as01(created_alert is not None),
        "notified": (as01(created_alert.notified) if created_alert is not None else 0),
    }


@router.post(
    "/{device_id}/reset",
    dependencies=[Depends(require_admin_api_key)],
)
async def reset_device(
    device_id: str,
    clear_logs: int = Query(
        default=0,
        ge=0,
        le=1,
    ),
) -> dict:
    device = await device_service.reset_device_to_normal(device_id)

    if clear_logs == 1:
        logs = await SensorLog.find(SensorLog.device_id == device_id).to_list()

        for log in logs:
            await log.delete()

        alerts = await Alert.find(Alert.device_id == device_id).to_list()

        for alert in alerts:
            await alert.delete()

    await ws_manager.broadcast(
        device_id,
        {
            "event": "sensor_update",
            "data": {
                "device_id": device.device_id,
                "timestamp": int(time.time()),
                "water_flow": as01(device.water_flow),
                "human_present": as01(device.human_present),
                "water_detected": as01(device.water_detected),
                "alert": as01(device.alert),
                "status": device.condition_status,
                "running_duration_sec": (device.running_duration_sec or 0),
                "flow_rate_lpm": device.flow_rate_lpm,
            },
        },
    )

    return {
        "ok": 1,
        "device_id": device.device_id,
        "status": device.condition_status,
        "water_flow": as01(device.water_flow),
        "human_present": as01(device.human_present),
        "water_detected": as01(device.water_detected),
        "alert": as01(device.alert),
        "running_duration_sec": (device.running_duration_sec or 0),
        "clear_logs": clear_logs,
    }
