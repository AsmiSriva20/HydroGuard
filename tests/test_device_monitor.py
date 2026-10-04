from unittest.mock import AsyncMock

import pytest

from app.models.payloads import SensorPayload
from app.services import device_service
from app.services.device_service import is_device_stale


def test_device_is_online_when_recently_seen():
    assert (
        is_device_stale(
            last_seen=970,
            offline_after_sec=60,
            now=1000,
        )
        is False
    )


def test_device_is_offline_at_exact_timeout():
    assert (
        is_device_stale(
            last_seen=940,
            offline_after_sec=60,
            now=1000,
        )
        is True
    )


def test_device_is_offline_after_timeout():
    assert (
        is_device_stale(
            last_seen=939,
            offline_after_sec=60,
            now=1000,
        )
        is True
    )


def test_device_without_last_seen_is_stale():
    assert (
        is_device_stale(
            last_seen=None,
            offline_after_sec=60,
            now=1000,
        )
        is True
    )


class FakeDevice:
    def __init__(
        self,
        device_id: str,
        status: str,
        last_seen: int | None,
    ):
        self.device_id = device_id
        self.status = status
        self.last_seen = last_seen
        self.abnormal_started_at = None
        self.save = AsyncMock()


def _unattended_payload(timestamp: int, running_duration_sec: int = 0) -> SensorPayload:
    return SensorPayload(
        device_id="device01",
        timestamp=timestamp,
        water_flow=1,
        human_present=0,
        water_detected=0,
        running_duration_sec=running_duration_sec,
    )


def test_real_device_duration_uses_one_x_time_by_default():
    device = FakeDevice(
        device_id="device01",
        status="ONLINE",
        last_seen=1000,
    )

    first = _unattended_payload(timestamp=1000)
    second = _unattended_payload(timestamp=1030)

    assert device_service._calculate_running_duration(first, device) == 0
    assert device_service._calculate_running_duration(second, device) == 30


def test_demo_duration_can_use_time_scale_without_changing_default():
    device = FakeDevice(
        device_id="device01",
        status="ONLINE",
        last_seen=1000,
    )

    first = _unattended_payload(timestamp=1000)
    second = _unattended_payload(timestamp=1030)

    assert device_service._calculate_running_duration(first, device, time_scale=10) == 0
    assert device_service._calculate_running_duration(second, device, time_scale=10) == 300


def test_payload_duration_is_kept_when_it_is_higher_than_elapsed_time():
    device = FakeDevice(
        device_id="device01",
        status="ONLINE",
        last_seen=1000,
    )
    device.abnormal_started_at = 1000

    payload = _unattended_payload(
        timestamp=1010,
        running_duration_sec=45,
    )

    assert device_service._calculate_running_duration(payload, device) == 45


def test_invalid_time_scale_is_rejected():
    device = FakeDevice(
        device_id="device01",
        status="ONLINE",
        last_seen=1000,
    )

    with pytest.raises(ValueError):
        device_service._calculate_running_duration(
            _unattended_payload(timestamp=1000),
            device,
            time_scale=0,
        )


@pytest.mark.asyncio
async def test_stale_online_device_is_marked_offline(monkeypatch):
    device = FakeDevice(
        device_id="device01",
        status="ONLINE",
        last_seen=900,
    )

    monkeypatch.setattr(
        device_service,
        "list_devices",
        AsyncMock(return_value=[device]),
    )

    monkeypatch.setattr(
        device_service,
        "is_device_stale",
        lambda last_seen, offline_after_sec: True,
    )

    result = await device_service.mark_stale_devices_offline(60)

    assert device.status == "OFFLINE"
    device.save.assert_awaited_once()
    assert result == ["device01"]


@pytest.mark.asyncio
async def test_recent_online_device_stays_online(monkeypatch):
    device = FakeDevice(
        device_id="device01",
        status="ONLINE",
        last_seen=990,
    )

    monkeypatch.setattr(
        device_service,
        "list_devices",
        AsyncMock(return_value=[device]),
    )

    monkeypatch.setattr(
        device_service,
        "is_device_stale",
        lambda last_seen, offline_after_sec: False,
    )

    result = await device_service.mark_stale_devices_offline(60)

    assert device.status == "ONLINE"
    device.save.assert_not_awaited()
    assert result == []


@pytest.mark.asyncio
async def test_already_offline_device_is_ignored(monkeypatch):
    device = FakeDevice(
        device_id="device01",
        status="OFFLINE",
        last_seen=800,
    )

    monkeypatch.setattr(
        device_service,
        "list_devices",
        AsyncMock(return_value=[device]),
    )

    result = await device_service.mark_stale_devices_offline(60)

    assert device.status == "OFFLINE"
    device.save.assert_not_awaited()
    assert result == []
