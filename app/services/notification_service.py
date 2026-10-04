import logging

import httpx

from app.core.config import Settings
from app.models.alert import Alert

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _format_message(alert: Alert) -> str:
    """Format the persisted severity and reason for Telegram."""

    return (
        f"HydroGuard alert\nDevice: {alert.device_id}\n"
        f"State: {alert.alert_type}\nSeverity: {alert.severity}\n"
        f"Duration: {alert.duration_sec}s\n{alert.message}\nPlease inspect this location."
    )


async def send_alert_notification(alert: Alert, settings: Settings) -> bool:
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id

    if not token or not chat_id:
        logger.debug("telegram not configured; skipping notification")
        return False

    url = _TELEGRAM_API.format(token=token)

    payload = {
        "chat_id": chat_id,
        "text": _format_message(alert),
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

        logger.info("telegram notification sent for alert device=%s", alert.device_id)
        return True

    except httpx.HTTPStatusError as error:
        logger.warning(
            "telegram send failed with status=%d",
            error.response.status_code,
        )
        return False

    except httpx.RequestError:
        logger.warning("telegram request failed")
        return False
