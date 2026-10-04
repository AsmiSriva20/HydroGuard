# Security Notes

## Current Controls

The current project includes a few basic security checks:

- admin write endpoints use an `X-API-Key` outside local development
- the React build does not contain the admin API key
- public demo routes accept only predefined scenarios for one configured demo device
- public demo routes cannot clear logs and do not send Telegram notifications
- CORS uses an explicit list of allowed origins
- MQTT payloads are validated with Pydantic
- MQTT topic device IDs are checked against payload device IDs
- stale timestamps are rejected
- oversized MQTT messages are rejected
- Telegram credentials are loaded from environment variables
- Telegram HTTP errors are logged without the token-bearing request URL
- `.env` files are ignored by Git

## Public Demo Boundary

The hosted dashboard is intentionally usable without a login, but it does not receive an admin secret.

The public routes are limited to:

```text
POST /api/demo/devices/{device_id}/scenario/{scenario}
POST /api/demo/devices/{device_id}/reset
```

The backend checks that `device_id` matches `DEMO_DEVICE_ID`. The scenario value is an enum with only six allowed states, so the browser cannot send arbitrary sensor payloads or timestamps through these endpoints.

The original admin routes remain separate and still require `X-API-Key` in production.

## MQTT

The local Mosquitto setup currently does not use authentication or TLS.

For a real deployment I would add:

- device credentials
- TLS
- topic-level permissions
- separate credentials for each device

## Application Access

A larger system would also need:

- user login
- role-based permissions
- audit logs
- session handling
- shared/distributed rate limiting if the service runs on multiple instances

## Data

A real deployment should also define:

- database access rules
- backup procedures
- retention periods
- secret storage
- HTTPS configuration