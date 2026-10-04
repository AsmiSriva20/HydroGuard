from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("")
async def configuration() -> dict:
    settings = get_settings()
    return {
        "name": settings.app_name,
        "unattended_threshold_sec": settings.alert_duration_threshold_sec,
        "offline_timeout_sec": settings.device_offline_after_sec,
        "alert_cooldown_sec": settings.alert_cooldown_sec,
        "automatic_shutoff_enabled": settings.automatic_shutoff_enabled,
        "mqtt_enabled": settings.mqtt_enabled,
        "demo_enabled": settings.demo_public_actions_enabled,
        "demo_device_id": settings.demo_device_id,
    }
