import time
from collections import deque
from enum import StrEnum

from fastapi import APIRouter, HTTPException, status

from app.core.config import Settings, get_settings
from app.models.payloads import (
    SensorPayload,
    derive_condition_status,
    expected_alert_value,
)
from app.services import device_service, ingestion_service
from app.services.websocket_manager import ws_manager

router = APIRouter(
    prefix="/api/demo",
    tags=["demo"],
)


_demo_action_times: deque[float] = deque()
_DEMO_RATE_WINDOW_SEC = 60.0


class DemoScenario(StrEnum):
    NORMAL = "NORMAL"
    NORMAL_FLOW = "NORMAL_FLOW"
    WARNING = "WARNING"
    ALERT = "ALERT"
    LEAK = "LEAK"
    CRITICAL = "CRITICAL"


def _require_public_demo(settings: Settings, device_id: str) -> None:
    if not settings.demo_public_actions_enabled or device_id != settings.demo_device_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="public demo action is not available for this device",
        )


def _enforce_public_demo_rate_limit(
    settings: Settings,
    now: float | None = None,
) -> None:
    current_time = time.monotonic() if now is None else now
    cutoff = current_time - _DEMO_RATE_WINDOW_SEC

    while _demo_action_times and _demo_action_times[0] <= cutoff:
        _demo_action_times.popleft()

    if len(_demo_action_times) >= settings.demo_rate_limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="public demo rate limit exceeded",
            headers={"Retry-After": "60"},
        )

    _demo_action_times.append(current_time)


def build_demo_payload(
    scenario: DemoScenario,
    device_id: str,
    timestamp: int,
    threshold_sec: int,
) -> SensorPayload:
    warning_duration = max(threshold_sec - 1, 0)
    alert_duration = max(threshold_sec, 0)

    values = {
        DemoScenario.NORMAL: {
            "water_flow": 0,
            "human_present": 0,
            "water_detected": 0,
            "running_duration_sec": 0,
            "flow_rate_lpm": 0.0,
        },
        DemoScenario.NORMAL_FLOW: {
            "water_flow": 1,
            "human_present": 1,
            "water_detected": 0,
            "running_duration_sec": 0,
            "flow_rate_lpm": 0.2,
        },
        DemoScenario.WARNING: {
            "water_flow": 1,
            "human_present": 0,
            "water_detected": 0,
            "running_duration_sec": warning_duration,
            "flow_rate_lpm": 0.3,
        },
        DemoScenario.ALERT: {
            "water_flow": 1,
            "human_present": 0,
            "water_detected": 0,
            "running_duration_sec": alert_duration,
            "flow_rate_lpm": 0.4,
        },
        DemoScenario.LEAK: {
            "water_flow": 0,
            "human_present": 0,
            "water_detected": 1,
            "running_duration_sec": 0,
            "flow_rate_lpm": 0.0,
        },
        DemoScenario.CRITICAL: {
            "water_flow": 1,
            "human_present": 0,
            "water_detected": 1,
            "running_duration_sec": 0,
            "flow_rate_lpm": 0.4,
        },
    }[scenario]

    return SensorPayload(
        device_id=device_id,
        timestamp=timestamp,
        alert=0,
        **values,
    )


@router.post("/devices/{device_id}/scenario/{scenario}")
async def run_demo_scenario(
    device_id: str,
    scenario: DemoScenario,
) -> dict:
    settings = get_settings()
    _require_public_demo(settings, device_id)
    _enforce_public_demo_rate_limit(settings)

    payload = build_demo_payload(
        scenario=scenario,
        device_id=device_id,
        timestamp=int(time.time()),
        threshold_sec=settings.alert_duration_threshold_sec,
    )

    try:
        device, created_alert = await ingestion_service.ingest(
            payload, settings, time_scale=settings.demo_time_scale, send_notification=False
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    condition_status = derive_condition_status(payload, settings.alert_duration_threshold_sec)

    return {
        "ok": 1,
        "device_id": device_id,
        "status": condition_status.value,
        "water_flow": payload.water_flow,
        "human_present": payload.human_present,
        "water_detected": payload.water_detected,
        "alert": expected_alert_value(condition_status),
        "running_duration_sec": payload.running_duration_sec,
        "flow_rate_lpm": payload.flow_rate_lpm,
        "created_alert": 1 if created_alert is not None else 0,
        "notified": 0,
    }


@router.post("/devices/{device_id}/reset")
async def reset_demo_device(
    device_id: str,
) -> dict:
    settings = get_settings()
    _require_public_demo(settings, device_id)
    _enforce_public_demo_rate_limit(settings)

    device = await device_service.reset_device_to_normal(device_id)

    await ws_manager.broadcast(
        device_id,
        {
            "event": "sensor_update",
            "data": {
                "device_id": device.device_id,
                "timestamp": int(time.time()),
                "water_flow": 0,
                "human_present": 0,
                "water_detected": 0,
                "alert": 0,
                "status": device.condition_status,
                "running_duration_sec": 0,
                "flow_rate_lpm": device.flow_rate_lpm,
            },
        },
    )

    return {
        "ok": 1,
        "device_id": device.device_id,
        "status": device.condition_status,
        "water_flow": 0,
        "human_present": 0,
        "water_detected": 0,
        "alert": 0,
        "running_duration_sec": 0,
    }
