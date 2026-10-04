# Alert workflow

HydroGuard persists one alert for each active device/state episode. Severity is WARNING, HIGH or CRITICAL. Telegram repeats are limited by the configured cooldown; increases in severity are immediate.

Operators acknowledge using `POST /api/alerts/{alert_id}/acknowledge` with the server-side admin key. Acknowledgement does not change sensor readings. A state change automatically resolves obsolete alerts; WebSocket events update connected dashboards.

Future extensions may record operator identity, investigation notes and valve feedback. These are optional and do not affect the current detection workflow.
