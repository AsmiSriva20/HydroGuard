from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "HydroGuard"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "smart_water"

    mqtt_enabled: bool = True
    mqtt_tls: bool = False
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_client_id: str = "fastapi-backend"
    mqtt_topic_sensor: str = "home/+/+/sensor"
    mqtt_topic_alert: str = "home/+/+/alert"
    mqtt_topic_status: str = "home/+/+/status"

    admin_api_key: str = ""

    demo_public_actions_enabled: bool = False
    demo_device_id: str = Field(
        default="device01",
        pattern=r"^[a-zA-Z0-9_-]{1,32}$",
    )

    demo_rate_limit_per_minute: int = Field(default=30, ge=1, le=600)

    cors_allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    alert_duration_threshold_sec: int = Field(default=300, ge=1)
    alert_cooldown_sec: int = Field(default=300, ge=0)
    automatic_shutoff_enabled: bool = False
    critical_flow_rate_lpm: float = Field(default=0.3, ge=0)
    demo_time_scale: int = Field(default=10, ge=1)

    timestamp_skew_past_sec: int = 3600
    timestamp_skew_future_sec: int = 300
    mqtt_max_payload_bytes: int = 512

    device_offline_after_sec: int = Field(default=60, ge=1)
    device_status_check_interval_sec: int = Field(default=10, ge=1)

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
