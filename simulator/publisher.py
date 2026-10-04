import json
import logging
import ssl
import time
from contextlib import asynccontextmanager
from typing import Any

import aiomqtt

from simulator.config import SimulatorConfig

logger = logging.getLogger(__name__)


def now_epoch() -> int:
    return int(time.time())


@asynccontextmanager
async def mqtt_client(config: SimulatorConfig, client_id: str):
    kwargs: dict[str, Any] = {
        "hostname": config.mqtt_host,
        "port": config.mqtt_port,
        "identifier": client_id,
    }
    if config.mqtt_tls:
        kwargs["tls_context"] = ssl.create_default_context()
    if config.mqtt_username:
        kwargs["username"] = config.mqtt_username
    if config.mqtt_password:
        kwargs["password"] = config.mqtt_password
    async with aiomqtt.Client(**kwargs) as client:
        logger.info(
            "simulator connected to %s:%d as %s", config.mqtt_host, config.mqtt_port, client_id
        )
        yield client


async def publish_sensor(
    client: aiomqtt.Client,
    *,
    location: str,
    device_id: str,
    water_flow: bool,
    water_detected: bool = False,
    human_present: bool,
    running_duration_sec: int,
    flow_rate_lpm: float | None = None,
) -> None:
    topic = f"home/{location}/{device_id}/sensor"
    payload: dict[str, Any] = {
        "device_id": device_id,
        "timestamp": now_epoch(),
        "water_flow": water_flow,
        "water_detected": water_detected,
        "human_present": human_present,
        "running_duration_sec": running_duration_sec,
    }
    if flow_rate_lpm is not None:
        payload["flow_rate_lpm"] = flow_rate_lpm
    await client.publish(topic, payload=json.dumps(payload))
    logger.info(
        "sensor -> %s water=%s human=%s running=%ds",
        device_id,
        water_flow,
        human_present,
        running_duration_sec,
    )


async def publish_status(
    client: aiomqtt.Client,
    *,
    location: str,
    device_id: str,
    status: str,
    uptime_sec: int,
    firmware_version: str | None = None,
) -> None:
    topic = f"home/{location}/{device_id}/status"
    payload: dict[str, Any] = {
        "device_id": device_id,
        "timestamp": now_epoch(),
        "status": status,
        "uptime_sec": uptime_sec,
    }
    if firmware_version is not None:
        payload["firmware_version"] = firmware_version
    await client.publish(topic, payload=json.dumps(payload), qos=1, retain=True)
    logger.info("status -> %s %s uptime=%ds", device_id, status, uptime_sec)


async def publish_alert(
    client: aiomqtt.Client,
    *,
    location: str,
    device_id: str,
    duration_sec: int,
    strength: str = "HIGH",
    alert_type: str = "WATER_RUNNING_NO_HUMAN",
) -> None:
    topic = f"home/{location}/{device_id}/alert"
    payload = {
        "device_id": device_id,
        "timestamp": now_epoch(),
        "alert_type": alert_type,
        "duration_sec": duration_sec,
        "strength": strength,
    }
    await client.publish(topic, payload=json.dumps(payload), qos=1)
    logger.info("alert -> %s duration=%ds strength=%s", device_id, duration_sec, strength)
