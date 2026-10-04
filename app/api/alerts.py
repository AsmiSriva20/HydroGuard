from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import require_admin_api_key
from app.models.alert import Alert
from app.services import alert_service
from app.services.websocket_manager import ws_manager

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def as01(value: int | bool | None) -> int:
    return 1 if value in (1, True) else 0


@router.get("")
async def list_alerts(
    device_id: str | None = Query(default=None),
    start_time: int | None = Query(default=None, ge=0),
    end_time: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict]:
    alerts = await alert_service.list_alerts(device_id, start_time, end_time, limit)

    return [alert_service.serialize_alert(alert) for alert in alerts]


@router.post("/{alert_id}/acknowledge", dependencies=[Depends(require_admin_api_key)])
async def acknowledge(alert_id: str) -> dict:
    alert = await Alert.find_one(Alert.alert_id == alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    alert.acknowledged = True
    await alert.save()
    await ws_manager.broadcast(
        alert.device_id,
        {"event": "ALERT_ACKNOWLEDGED", "data": alert_service.serialize_alert(alert)},
    )
    return alert_service.serialize_alert(alert)
