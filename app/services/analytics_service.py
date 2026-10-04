"""Integrate the previous sample until the next sample; never extrapolate offline gaps."""

import time
from datetime import UTC, datetime

from app.models.alert import Alert
from app.models.device import Device
from app.models.sensor import SensorLog


def usage_segments(previous, timestamp: int, max_gap: int) -> list[dict]:
    if previous is None or not 0 < timestamp - previous.timestamp <= max_gap:
        return []
    rate = (previous.flow_rate_lpm or 0) if previous.water_flow else 0
    wasted = not previous.human_present
    segments = []
    start = previous.timestamp
    while start < timestamp:
        end = min(timestamp, (start // 86400 + 1) * 86400)
        volume = rate * (end - start) / 60
        segments.append(
            {
                "day": start // 86400 * 86400,
                "used_litres": volume,
                "wasted_litres": volume if wasted else 0,
            }
        )
        start = end
    return segments


async def volume_rows(
    start: int = 0, end: int | None = None, device_id: str | None = None, group: str = "day"
) -> list[dict]:
    match = {"timestamp": {"$gte": start}}
    if device_id:
        match["device_id"] = device_id
    segment_match = {"usage_segments.day": {"$gte": start}}
    if end is not None:
        segment_match["usage_segments.day"]["$lt"] = end
    key = "$device_id" if group == "device_id" else "$usage_segments.day"
    if group == "week":
        # Epoch Thursday shifted to Monday for calendar-week buckets.
        key = {
            "$subtract": [
                "$usage_segments.day",
                {"$mod": [{"$add": ["$usage_segments.day", 259200]}, 604800]},
            ]
        }
    return await SensorLog.aggregate(
        [
            {"$match": match},
            {"$unwind": "$usage_segments"},
            {"$match": segment_match},
            {
                "$group": {
                    "_id": key,
                    "used_litres": {"$sum": "$usage_segments.used_litres"},
                    "wasted_litres": {"$sum": "$usage_segments.wasted_litres"},
                }
            },
            {"$sort": {"_id": 1}},
        ]
    ).to_list()


async def summary(device_id: str | None = None) -> dict:
    today = int(time.time()) // 86400 * 86400
    rows = await volume_rows(device_id=device_id)
    today_rows = await volume_rows(start=today, end=today + 86400, device_id=device_id)
    devices = await Device.find({"device_id": device_id} if device_id else {}).to_list()
    incident_match = {"incident": True}
    if device_id:
        incident_match["device_id"] = device_id
    incidents = await SensorLog.aggregate(
        [{"$match": incident_match}, {"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    ).to_list()
    counts = {r["_id"]: r["count"] for r in incidents}
    active_match = {"resolved": False}
    if device_id:
        active_match["device_id"] = device_id
    leak_match = {
        **incident_match,
        "timestamp": {"$gte": today, "$lt": today + 86400},
        "status": {"$in": ["LEAK", "CRITICAL"]},
    }
    return {
        "total_used_litres": sum(r["used_litres"] for r in rows),
        "total_wasted_litres": sum(r["wasted_litres"] for r in rows),
        "today_used_litres": sum(r["used_litres"] for r in today_rows),
        "today_wasted_litres": sum(r["wasted_litres"] for r in today_rows),
        "active_devices": sum(d.status == "ONLINE" for d in devices),
        "offline_devices": sum(d.status == "OFFLINE" for d in devices),
        "active_alerts": await Alert.find(active_match).count(),
        "leak_incidents_today": await SensorLog.find(leak_match).count(),
        "incidents": {
            s: counts.get(s, 0) for s in ["WARNING", "WASTAGE_ALERT", "LEAK", "CRITICAL"]
        },
        "timezone": "UTC",
    }


def serialize_rows(rows: list[dict], group: str) -> list[dict]:
    return [
        {
            group: (
                row["_id"]
                if group == "device_id"
                else datetime.fromtimestamp(row["_id"], UTC).date().isoformat()
            ),
            "used_litres": round(row["used_litres"], 4),
            "wasted_litres": round(row["wasted_litres"], 4),
        }
        for row in rows
    ]
