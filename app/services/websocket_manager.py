import asyncio
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, device_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[device_id].add(websocket)
        logger.info(
            "ws connected: device_id=%s total=%d", device_id, len(self._connections[device_id])
        )

    async def disconnect(self, device_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[device_id].discard(websocket)
            if not self._connections[device_id]:
                self._connections.pop(device_id, None)
        logger.info("ws disconnected: device_id=%s", device_id)

    async def broadcast(self, device_id: str, message: dict[str, Any]) -> None:
        names = {
            "sensor_update": "DEVICE_TELEMETRY_UPDATED",
            "device_status": "DEVICE_STATUS_CHANGED",
            "alert_created": "NEW_ALERT",
        }
        message = {
            **message,
            "type": (
                "DEVICE_OFFLINE"
                if message.get("event") == "device_status"
                and message.get("data", {}).get("status") == "OFFLINE"
                else names.get(message.get("event"), message.get("event"))
            ),
        }
        async with self._lock:
            targets = list(
                self._connections.get(device_id, set()) | self._connections.get("*", set())
            )
        if not targets:
            return
        results = await asyncio.gather(
            *(ws.send_json(message) for ws in targets),
            return_exceptions=True,
        )
        for ws, result in zip(targets, results, strict=False):
            if isinstance(result, Exception):
                logger.warning("ws send failed, dropping: %s", result)
                await self.disconnect(device_id, ws)


ws_manager = WebSocketManager()
