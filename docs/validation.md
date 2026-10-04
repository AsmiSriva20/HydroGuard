# HydroGuard validation

Verified locally on 4 October 2026:

- 91 backend tests pass, including state transitions, unattended timing, offline detection, previous-sample usage integration, midnight splitting, cooldown, MQTT replay rejection, persistence/API analytics, alert acknowledgement/resolution, retained-message handling and optional valve command boundaries.
- Ruff and Black checks pass. Beanie's lazy-model dependency emits Pydantic deprecation warnings; these do not fail the tests.
- React ESLint and Vite production build pass. Compatible npm audit patch applied; audit reports zero vulnerabilities.
- `docker compose config --quiet` succeeds. All four services build and start; MongoDB and Mosquitto health checks pass.
- Named five-device simulator run completes against the real MQTT broker.
- `scripts/check_stack.py` passes against the live stack: MQTT ingestion, independent device states, persisted volumes, wastage/critical alerts, acknowledgement and resolution, frontend HTTP and nginx WebSocket forwarding.
- Silent simulator device becomes OFFLINE after the configured 60-second timeout; fresh MQTT telemetry restores ONLINE and resolves its offline alert.
- A real local dashboard screenshot was captured and reviewed.

External Telegram delivery and physical ESP32/valve hardware were not tested. Render deployment and removal of the previous hosted service require connected Render account access and a reachable MongoDB URI. The new Blueprint is prepared; it does not delete remote resources by itself.
