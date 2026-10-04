# HydroGuard dashboard

React/Vite dashboard for the HydroGuard FastAPI backend. It preserves the original monitoring panels and adds device overview, persisted usage cards, daily/weekly charts and all-device WebSocket updates.

Use Node 22.13+ or 24+:

```sh
npm ci
npm run dev
npm run lint
npm run build
```

Vite proxies `/api`, `/health` and `/ws` to localhost:8000. Docker builds this app automatically and nginx proxies the same paths to the backend. The Render Dockerfile serves the bundle from FastAPI. Keep `VITE_API_BASE` empty for same-origin deployment; set it only for a separate backend origin. Never include an admin API key in a build.

See the [root README](../README.md) for simulator, configuration and deployment instructions.
