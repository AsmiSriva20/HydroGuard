import logging

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import Settings
from app.models.alert import Alert
from app.models.device import Device
from app.models.sensor import SensorLog

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None


async def init_db(settings: Settings) -> AsyncIOMotorClient:
    global _client
    _client = AsyncIOMotorClient(settings.mongo_uri, uuidRepresentation="standard")
    db = _client[settings.mongo_db]
    await init_beanie(database=db, document_models=[Device, SensorLog, Alert])
    logger.info("mongo connected: db=%s", settings.mongo_db)
    return _client


def close_db() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("mongo connection closed")
