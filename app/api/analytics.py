import time

from fastapi import APIRouter, Query

from app.services import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary")
async def summary() -> dict:
    return await analytics_service.summary()


@router.get("/devices/{device_id}")
async def device_summary(device_id: str) -> dict:
    return await analytics_service.summary(device_id)


@router.get("/devices")
async def devices() -> list[dict]:
    return analytics_service.serialize_rows(
        await analytics_service.volume_rows(group="device_id"), "device_id"
    )


@router.get("/daily")
async def daily(
    days: int = Query(default=7, ge=1, le=366), device_id: str | None = None
) -> list[dict]:
    start = int(time.time()) // 86400 * 86400 - (days - 1) * 86400
    return analytics_service.serialize_rows(
        await analytics_service.volume_rows(start=start, device_id=device_id), "day"
    )


@router.get("/weekly")
async def weekly(
    weeks: int = Query(default=4, ge=1, le=52), device_id: str | None = None
) -> list[dict]:
    today = int(time.time()) // 86400 * 86400
    start = today - (today + 259200) % 604800 - (weeks - 1) * 604800
    return analytics_service.serialize_rows(
        await analytics_service.volume_rows(start=start, device_id=device_id, group="week"), "week"
    )
