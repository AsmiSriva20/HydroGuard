from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

DEVICE_ID_RE = r"^[a-zA-Z0-9_-]{1,32}$"
BinaryFlag = Annotated[int, Field(ge=0, le=1)]


class AlertType(StrEnum):
    WATER_RUNNING_NO_HUMAN = "WATER_RUNNING_NO_HUMAN"
    ALERT = "ALERT"
    CRITICAL = "CRITICAL"


class AlertStrength(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DeviceStatusEnum(StrEnum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"


class ConditionStatus(StrEnum):
    NORMAL = "NORMAL"
    NORMAL_FLOW = "NORMAL_FLOW"
    WARNING = "WARNING"
    WASTAGE_ALERT = "WASTAGE_ALERT"
    ALERT = "WASTAGE_ALERT"
    LEAK = "LEAK"
    CRITICAL = "CRITICAL"
    OFFLINE = "OFFLINE"

    @classmethod
    def _missing_(cls, value):
        if value == "ALERT":
            return cls.WASTAGE_ALERT
        return None


class _StrictBase(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
    )


class SensorPayload(_StrictBase):
    device_id: str = Field(pattern=DEVICE_ID_RE)
    timestamp: int = Field(ge=0)

    water_flow: BinaryFlag = Field(
        default=0, validation_alias=AliasChoices("water_flow", "water_flowing")
    )
    human_present: BinaryFlag = 0
    water_detected: BinaryFlag = Field(
        default=0, validation_alias=AliasChoices("water_detected", "leak_detected")
    )
    alert: BinaryFlag = 0

    status: ConditionStatus | None = None
    running_duration_sec: int = Field(
        default=0,
        ge=0,
    )
    flow_rate_lpm: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def timestamp_from_iso(cls, value):
        if isinstance(value, str) and not value.isdigit():
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("ISO timestamps require a timezone")
            return int(parsed.timestamp())
        return value

    @field_validator(
        "water_flow",
        "human_present",
        "water_detected",
        "alert",
        mode="before",
    )
    @classmethod
    def only_accept_0_or_1(
        cls,
        value: object,
    ) -> int:
        if isinstance(value, bool):
            return 1 if value else 0

        if isinstance(value, int) and value in (0, 1):
            return value

        raise ValueError("sensor values must be 0 or 1")


class AlertPayload(_StrictBase):
    device_id: str = Field(pattern=DEVICE_ID_RE)
    timestamp: int = Field(ge=0)
    alert_type: AlertType
    duration_sec: int = Field(ge=0)
    strength: AlertStrength


class StatusPayload(_StrictBase):
    device_id: str = Field(pattern=DEVICE_ID_RE)
    timestamp: int = Field(ge=0)
    status: DeviceStatusEnum
    uptime_sec: int = Field(ge=0)
    free_heap: int | None = Field(
        default=None,
        ge=0,
    )
    rssi: int | None = Field(
        default=None,
        le=0,
    )
    firmware_version: str | None = None


class DeviceRegisterRequest(_StrictBase):
    device_id: str = Field(pattern=DEVICE_ID_RE)
    device_name: str | None = Field(default=None, min_length=1, max_length=64)
    location: str = Field(
        min_length=1,
        max_length=64,
    )


def compute_strength(
    duration_sec: int,
) -> AlertStrength:
    if duration_sec >= 1200:
        return AlertStrength.HIGH

    if duration_sec >= 600:
        return AlertStrength.MEDIUM

    return AlertStrength.LOW


def derive_condition_status(payload: SensorPayload, threshold_sec: int) -> ConditionStatus:
    from app.core.config import get_settings
    from app.services.state_machine import derive_condition_status as derive

    return derive(payload, threshold_sec, get_settings().critical_flow_rate_lpm)


def should_notify_user(
    status: ConditionStatus,
) -> bool:
    return status in {
        ConditionStatus.WARNING,
        ConditionStatus.ALERT,
        ConditionStatus.LEAK,
        ConditionStatus.CRITICAL,
        ConditionStatus.OFFLINE,
    }


def expected_alert_value(
    status: ConditionStatus,
) -> int:
    return 1 if should_notify_user(status) else 0
