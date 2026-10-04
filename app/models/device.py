from typing import Annotated

from beanie import Document, Indexed
from pydantic import Field

from app.database.collections import DEVICES


class Device(Document):
    device_id: Annotated[str, Indexed(unique=True)]
    location: str | None = None
    device_name: str | None = None
    last_telemetry_at: int | None = None
    alert_sent_at: dict[str, int] = Field(default_factory=dict)

    status: str = "OFFLINE"
    condition_status: str | None = None

    last_seen: int | None = None
    uptime_sec: int | None = None
    firmware_version: str | None = None

    water_flow: int | None = None
    human_present: int | None = None
    water_detected: int | None = None
    alert: int | None = None

    running_duration_sec: int | None = None
    flow_rate_lpm: float | None = None

    abnormal_started_at: int | None = Field(
        default=None,
        description="Unix time when flow with no human started.",
    )

    active_alert_at: int | None = Field(
        default=None,
        description="Unix time when an alert started.",
    )
    active_alert_status: str | None = None

    created_at: int

    class Settings:
        name = DEVICES
