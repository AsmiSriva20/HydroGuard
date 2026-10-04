"""Live smoke check: MQTT -> MongoDB/API -> nginx WebSocket and analytics.
Run after docker compose up: python scripts/check_stack.py
Uses new check_* device IDs and leaves their test history in the local database.
"""

import asyncio
import json
import sys
import time

import aiomqtt
import httpx
import websockets


async def main():
    suffix = str(int(time.time()))
    first, second = f"check_{suffix}", f"check_lab_{suffix}"
    async with httpx.AsyncClient(base_url="http://localhost:3000", timeout=15) as api:
        assert (await api.get("/health")).status_code == 200
        assert "HydroGuard" in (await api.get("/")).text
        config = (await api.get("/api/system")).json()
        threshold = config["unattended_threshold_sec"]
        async with websockets.connect("ws://localhost:3000/ws/dashboard") as socket:
            async with aiomqtt.Client(hostname="localhost", port=1883) as mqtt:

                async def publish(device, **values):
                    body = {"device_id": device, "timestamp": int(time.time()), **values}
                    await mqtt.publish(f"home/validation/{device}/sensor", json.dumps(body), qos=1)

                await publish(first, water_flow=True, human_present=False, flow_rate_lpm=6)
                event = json.loads(await asyncio.wait_for(socket.recv(), 15))
                assert event["type"] in {"NEW_ALERT", "DEVICE_TELEMETRY_UPDATED"}
                await asyncio.sleep(2)
                await publish(
                    first,
                    water_flow=True,
                    human_present=False,
                    flow_rate_lpm=6,
                    running_duration_sec=threshold,
                )
                await publish(second, water_flow=True, human_present=True, flow_rate_lpm=3)
                await asyncio.sleep(2)
                live = (await api.get(f"/api/devices/{first}/live")).json()
                assert live["status"] == "WASTAGE_ALERT", live
                assert (await api.get(f"/api/devices/{second}/live")).json()[
                    "status"
                ] == "NORMAL_FLOW"
                summary = (await api.get(f"/api/analytics/devices/{first}")).json()
                assert (
                    summary["total_used_litres"] > 0 and summary["total_wasted_litres"] > 0
                ), summary
                await publish(first, water_flow=True, water_detected=True, flow_rate_lpm=6)
                await asyncio.sleep(2)
                alerts = (await api.get(f"/api/alerts?device_id={first}")).json()
                critical = next(alert for alert in alerts if alert["alert_type"] == "CRITICAL")
                assert critical["severity"] == "CRITICAL"
                ack = await api.post(f"/api/alerts/{critical['alert_id']}/acknowledge")
                assert ack.status_code == 200 and ack.json()["acknowledged"]
                await publish(first, water_flow=False, water_detected=False, flow_rate_lpm=0)
                await asyncio.sleep(2)
                assert all(
                    alert["resolved"]
                    for alert in (await api.get(f"/api/alerts?device_id={first}")).json()
                )
                for route in ["summary", "daily", "weekly", "devices"]:
                    assert (await api.get(f"/api/analytics/{route}")).status_code == 200
                print(
                    "PASS: live MQTT, separate devices, persisted usage, wastage/critical rules, alert acknowledgement/resolution, frontend HTTP and WebSocket proxy"
                )
                print(f"Test devices: {first}, {second}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
