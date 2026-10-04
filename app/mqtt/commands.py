"""Optional control path. Commands are never retained or sent by public demos."""

import json
import logging
import ssl

import aiomqtt

from app.core.config import Settings


async def close_valve(device_id: str, settings: Settings) -> bool:
    if not settings.automatic_shutoff_enabled:
        return False
    try:
        async with aiomqtt.Client(
            hostname=settings.mqtt_host,
            port=settings.mqtt_port,
            username=settings.mqtt_username or None,
            password=settings.mqtt_password or None,
            tls_context=ssl.create_default_context() if settings.mqtt_tls else None,
        ) as client:
            await client.publish(
                f"hydroguard/device/{device_id}/commands",
                json.dumps({"command": "CLOSE_VALVE", "reason": "CRITICAL_LEAK"}),
                qos=1,
                retain=False,
            )
        return True
    except aiomqtt.MqttError:
        logging.getLogger(__name__).warning("Valve command delivery failed for %s", device_id)
        return False
