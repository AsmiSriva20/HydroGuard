import asyncio
import logging
import random

from simulator.config import SimulatorConfig
from simulator.publisher import (
    mqtt_client,
    now_epoch,
    publish_sensor,
    publish_status,
)

logger = logging.getLogger(__name__)


async def scenario_leak(
    config: SimulatorConfig,
    device_id: str,
    location: str,
    duration_sec: int = 360,
    tick_sec: float = 1.0,
) -> None:
    """Water flowing, no human, for `duration_sec` seconds.

    Backend should fire an alert at running_duration_sec == 300 (5 min).
    Use duration >= 310 to comfortably observe the alert.
    """
    logger.info("[leak] device=%s duration=%ds tick=%.2fs", device_id, duration_sec, tick_sec)
    boot = now_epoch()
    async with mqtt_client(config, client_id=f"sim-{device_id}") as client:
        await publish_status(
            client,
            location=location,
            device_id=device_id,
            status="ONLINE",
            uptime_sec=0,
            firmware_version="sim-1.0.0",
        )
        running = 0
        for _ in range(duration_sec):
            running += 1
            await publish_sensor(
                client,
                location=location,
                device_id=device_id,
                water_flow=True,
                human_present=False,
                running_duration_sec=running,
                flow_rate_lpm=4.7,
            )
            await asyncio.sleep(tick_sec)

        # cool-down: reset condition so duplicate-alert state clears
        for _ in range(3):
            await publish_sensor(
                client,
                location=location,
                device_id=device_id,
                water_flow=False,
                human_present=False,
                running_duration_sec=0,
            )
            await asyncio.sleep(tick_sec)
        await publish_status(
            client,
            location=location,
            device_id=device_id,
            status="OFFLINE",
            uptime_sec=now_epoch() - boot,
        )


async def scenario_normal(
    config: SimulatorConfig,
    device_id: str,
    location: str,
    duration_sec: int = 120,
    tick_sec: float = 1.0,
) -> None:
    """Random water_flow, mostly human present. No alert should fire."""
    logger.info("[normal] device=%s duration=%ds tick=%.2fs", device_id, duration_sec, tick_sec)
    boot = now_epoch()
    async with mqtt_client(config, client_id=f"sim-{device_id}") as client:
        await publish_status(
            client,
            location=location,
            device_id=device_id,
            status="ONLINE",
            uptime_sec=0,
            firmware_version="sim-1.0.0",
        )
        running = 0
        for _ in range(duration_sec):
            water = random.random() < 0.4
            human = random.random() < 0.75
            if water and not human:
                running += 1
            else:
                running = 0
            flow = round(random.uniform(2.0, 8.0), 2) if water else None
            await publish_sensor(
                client,
                location=location,
                device_id=device_id,
                water_flow=water,
                human_present=human,
                running_duration_sec=running,
                flow_rate_lpm=flow,
            )
            await asyncio.sleep(tick_sec)
        await publish_status(
            client,
            location=location,
            device_id=device_id,
            status="OFFLINE",
            uptime_sec=now_epoch() - boot,
        )


async def scenario_intermittent(
    config: SimulatorConfig,
    device_id: str,
    location: str,
    duration_sec: int = 180,
    tick_sec: float = 1.0,
) -> None:
    """Water cycles on/off; human always present. No alert should fire."""
    logger.info(
        "[intermittent] device=%s duration=%ds tick=%.2fs", device_id, duration_sec, tick_sec
    )
    boot = now_epoch()
    async with mqtt_client(config, client_id=f"sim-{device_id}") as client:
        await publish_status(
            client,
            location=location,
            device_id=device_id,
            status="ONLINE",
            uptime_sec=0,
            firmware_version="sim-1.0.0",
        )
        for tick in range(duration_sec):
            water = (tick // 15) % 2 == 0
            human = True
            running = 0
            flow = round(random.uniform(3.0, 6.0), 2) if water else None
            await publish_sensor(
                client,
                location=location,
                device_id=device_id,
                water_flow=water,
                human_present=human,
                running_duration_sec=running,
                flow_rate_lpm=flow,
            )
            await asyncio.sleep(tick_sec)
        await publish_status(
            client,
            location=location,
            device_id=device_id,
            status="OFFLINE",
            uptime_sec=now_epoch() - boot,
        )


async def scenario_fixed(
    config: SimulatorConfig,
    device_id: str,
    location: str,
    scenario: str,
    duration_sec: int = 360,
    tick_sec: float = 1,
) -> None:
    """Named deterministic scenarios use elapsed wall time, never tick count."""
    import json
    import time

    flags = {
        "normal": (False, False, False),
        "normal_usage": (True, True, False),
        "unattended_flow": (True, False, False),
        "leak": (False, False, True),
        "critical_leak": (True, False, True),
        "device_offline": (False, False, False),
    }
    water, human, leak = flags[scenario]
    async with mqtt_client(config, client_id=f"sim-{device_id}") as client:
        await publish_status(
            client,
            location=location,
            device_id=device_id,
            status="ONLINE",
            uptime_sec=0,
            firmware_version="sim-2.0",
        )
        await client.subscribe(f"hydroguard/device/{device_id}/commands")

        async def commands():
            async for message in client.messages:
                try:
                    body = json.loads(bytes(message.payload))
                except (ValueError, UnicodeDecodeError):
                    continue
                if body.get("command") == "CLOSE_VALVE":
                    nonlocal water
                    water = False
                    await client.publish(
                        f"hydroguard/device/{device_id}/ack",
                        json.dumps(
                            {"device_id": device_id, "command": "CLOSE_VALVE", "acknowledged": True}
                        ),
                        qos=1,
                    )
                    logger.info("Simulated valve closed: %s", device_id)

        command_task = asyncio.create_task(commands())
        start = time.monotonic()
        try:
            await publish_sensor(
                client,
                location=location,
                device_id=device_id,
                water_flow=water,
                human_present=human,
                water_detected=leak,
                running_duration_sec=0,
                flow_rate_lpm=4.7 if water else 0,
            )
            if scenario == "device_offline":
                # Remain silent; let the backend detect the missing heartbeat.
                await asyncio.sleep(duration_sec)
                return
            while time.monotonic() - start < duration_sec:
                await asyncio.sleep(tick_sec)
                elapsed = int(time.monotonic() - start)
                await publish_sensor(
                    client,
                    location=location,
                    device_id=device_id,
                    water_flow=water,
                    human_present=human,
                    water_detected=leak,
                    running_duration_sec=elapsed if water and not human and not leak else 0,
                    flow_rate_lpm=4.7 if water else 0,
                )
            await publish_status(
                client,
                location=location,
                device_id=device_id,
                status="OFFLINE",
                uptime_sec=int(time.monotonic() - start),
            )
        finally:
            command_task.cancel()
            try:
                await command_task
            except asyncio.CancelledError:
                pass


async def scenario_multi(
    config: SimulatorConfig, count: int = 5, duration_sec: int = 360, tick_sec: float = 1
) -> None:
    places = ["washroom_01", "washroom_02", "engineering_lab", "hostel_floor", "water_tank"]
    scenarios = ["normal_usage", "unattended_flow", "leak", "critical_leak", "device_offline"]
    await asyncio.gather(
        *(
            scenario_fixed(
                config,
                places[i] if i < len(places) else f"device_{i}",
                places[i % len(places)],
                scenarios[i % len(scenarios)],
                duration_sec,
                tick_sec,
            )
            for i in range(count)
        )
    )
