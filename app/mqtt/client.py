import asyncio
import logging
import ssl

import aiomqtt

from app.core.config import Settings
from app.mqtt.handlers import handle_message

logger = logging.getLogger(__name__)


async def run_subscriber(settings: Settings) -> None:
    """Long-running MQTT subscriber with exponential backoff reconnect."""
    backoff = 1
    max_backoff = 30

    while True:
        try:
            client_args = {
                "hostname": settings.mqtt_host,
                "port": settings.mqtt_port,
                "identifier": settings.mqtt_client_id,
            }
            if settings.mqtt_tls:
                client_args["tls_context"] = ssl.create_default_context()
            if settings.mqtt_username:
                client_args["username"] = settings.mqtt_username
            if settings.mqtt_password:
                client_args["password"] = settings.mqtt_password

            async with aiomqtt.Client(**client_args) as client:
                logger.info("mqtt connected: %s:%d", settings.mqtt_host, settings.mqtt_port)
                backoff = 1
                await client.subscribe(settings.mqtt_topic_sensor)
                await client.subscribe(settings.mqtt_topic_alert)
                await client.subscribe(settings.mqtt_topic_status)
                logger.info(
                    "subscribed: %s, %s, %s",
                    settings.mqtt_topic_sensor,
                    settings.mqtt_topic_alert,
                    settings.mqtt_topic_status,
                )

                async for message in client.messages:
                    try:
                        await handle_message(
                            str(message.topic),
                            bytes(message.payload),
                            settings,
                            retained=message.retain,
                        )
                    except Exception:
                        logger.exception("handler crashed on topic=%s", message.topic)

        except aiomqtt.MqttError as e:
            logger.warning("mqtt error: %s; reconnecting in %ds", e, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
        except asyncio.CancelledError:
            logger.info("mqtt subscriber cancelled")
            raise
