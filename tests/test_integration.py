"""In-memory persistence integration; live infrastructure is checked separately."""

import json
import time
from unittest.mock import AsyncMock

import pytest
from beanie import init_beanie
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.main import create_app
from app.models.alert import Alert
from app.models.device import Device
from app.models.sensor import SensorLog
from app.mqtt.handlers import handle_message
from app.services import alert_service, device_service, notification_service
from app.services.websocket_manager import ws_manager

mongomock_motor = pytest.importorskip("mongomock_motor")


@pytest.fixture
async def database(monkeypatch):
    await init_beanie(
        database=mongomock_motor.AsyncMongoMockClient().hydroguard,
        document_models=[Device, SensorLog, Alert],
    )
    monkeypatch.setattr(
        notification_service, "send_alert_notification", AsyncMock(return_value=True)
    )
    events = AsyncMock()
    monkeypatch.setattr(ws_manager, "broadcast", events)
    return events


@pytest.mark.asyncio
async def test_mqtt_persistence_analytics_alert_ack_and_resolution(database):
    settings = Settings(app_env="development", admin_api_key="", alert_duration_threshold_sec=300)
    now = int(time.time()) - 30

    async def send(timestamp, device="washroom_01", human=False, water=True, leak=False, rate=6):
        await handle_message(
            f"home/washroom/{device}/sensor",
            json.dumps(
                {
                    "device_id": device,
                    "timestamp": timestamp,
                    "water_flowing": water,
                    "human_present": human,
                    "leak_detected": leak,
                    "flow_rate_lpm": rate,
                }
            ).encode(),
            settings,
        )

    await send(now)
    await send(now + 20)
    await send(now + 20)  # replay is ignored
    await send(now + 10)  # older sample is ignored
    await send(now + 20, device="lab_01", human=True)
    assert await SensorLog.find(SensorLog.device_id == "washroom_01").count() == 2
    assert await Alert.find(Alert.device_id == "washroom_01").count() == 1
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        summary = (await client.get("/api/analytics/summary")).json()
        assert summary["total_used_litres"] == 2
        assert summary["total_wasted_litres"] == 2
        assert summary["active_devices"] == 2
        assert summary["incidents"]["WARNING"] == 1
        alerts = (await client.get("/api/alerts")).json()
        response = await client.post(f"/api/alerts/{alerts[0]['alert_id']}/acknowledge")
        assert response.status_code == 200
        assert response.json()["acknowledged"] is True
        for route in ["daily", "weekly", "devices", "devices/washroom_01"]:
            assert (await client.get(f"/api/analytics/{route}")).status_code == 200
    await send(now + 25, water=False, rate=0)
    assert (await Alert.find_one(Alert.device_id == "washroom_01")).resolved
    types = {call.args[1]["event"] for call in database.await_args_list}
    assert "sensor_update" in types and "alert_created" in types and "ALERT_RESOLVED" in types


@pytest.mark.asyncio
async def test_offline_and_recovery_resolve_alert(database):
    settings = Settings()
    now = int(time.time())
    await handle_message(
        "home/lab/lab_01/sensor",
        json.dumps({"device_id": "lab_01", "timestamp": now, "water_flow": False}).encode(),
        settings,
    )
    device = await device_service.get_device("lab_01")
    device.last_seen = now - 61
    await device.save()
    assert await device_service.mark_stale_devices_offline(60) == ["lab_01"]
    device = await device_service.get_device("lab_01")
    await alert_service.evaluate_state(device, "OFFLINE", now, 0, settings)
    await handle_message(
        "home/lab/lab_01/sensor",
        json.dumps({"device_id": "lab_01", "timestamp": now + 1}).encode(),
        settings,
    )
    assert (await device_service.get_device("lab_01")).status == "ONLINE"
    assert (await Alert.find_one(Alert.device_id == "lab_01")).resolved


@pytest.mark.asyncio
async def test_stale_retained_status_does_not_revive_device(database):
    settings = Settings()
    now = int(time.time())
    await handle_message(
        "home/lab/retained/sensor",
        json.dumps({"device_id": "retained", "timestamp": now}).encode(),
        settings,
    )
    device = await device_service.get_device("retained")
    device.status = "OFFLINE"
    device.last_seen = now - 120
    await device.save()
    await handle_message(
        "home/lab/retained/status",
        json.dumps(
            {"device_id": "retained", "timestamp": now - 120, "status": "ONLINE", "uptime_sec": 10}
        ).encode(),
        settings,
        retained=True,
    )
    device = await device_service.get_device("retained")
    assert device.status == "OFFLINE"
    assert device.last_seen == now - 120


@pytest.mark.asyncio
async def test_retained_alert_cannot_send_actuator_command(database):
    settings = Settings(automatic_shutoff_enabled=True)
    await handle_message(
        "home/lab/retained/alert",
        json.dumps(
            {
                "device_id": "retained",
                "timestamp": int(time.time()),
                "alert_type": "CRITICAL",
                "duration_sec": 0,
                "strength": "HIGH",
            }
        ).encode(),
        settings,
        retained=True,
    )
    assert await Alert.find_all().count() == 0


@pytest.mark.asyncio
async def test_valve_only_on_critical_entry_and_never_public_demo(database, monkeypatch):
    from app.models.payloads import SensorPayload
    from app.mqtt import commands
    from app.services import ingestion_service

    close = AsyncMock(return_value=True)
    monkeypatch.setattr(commands, "close_valve", close)
    settings = Settings(automatic_shutoff_enabled=True)
    now = int(time.time())

    def critical(device_id, timestamp):
        return SensorPayload(
            device_id=device_id,
            timestamp=timestamp,
            water_flow=True,
            water_detected=True,
            flow_rate_lpm=6,
        )

    await ingestion_service.ingest(critical("tank", now), settings)
    await ingestion_service.ingest(critical("tank", now + 1), settings)
    close.assert_awaited_once()
    await ingestion_service.ingest(critical("demo", now), settings, send_notification=False)
    close.assert_awaited_once()
