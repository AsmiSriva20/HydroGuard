from typing import Annotated
from uuid import uuid4

from beanie import Document, Indexed
from pydantic import Field
from pymongo import IndexModel

from app.database.collections import ALERTS


class Alert(Document):
    alert_id: Annotated[str, Indexed(unique=True)] = Field(default_factory=lambda: uuid4().hex)
    device_id: Annotated[str, Indexed()]
    alert_type: str
    strength: str
    duration_sec: int
    timestamp: Annotated[int, Indexed()]
    created_at: int
    notified: bool = False
    severity: str = "INFO"
    message: str = ""
    acknowledged: bool = False
    resolved: bool = False

    class Settings:
        name = ALERTS
        indexes = [
            IndexModel([("device_id", 1), ("resolved", 1), ("timestamp", -1)]),
            IndexModel([("severity", 1), ("acknowledged", 1)]),
        ]
