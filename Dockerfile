# Frontend build
FROM node:22-slim AS frontend-build

WORKDIR /build/frontend-react

COPY frontend-react/package.json frontend-react/package-lock.json* ./

RUN npm ci

COPY frontend-react/ ./

ENV VITE_API_BASE=""

RUN npm run build


# Backend
FROM python:3.11-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY app/ ./app/
COPY simulator/ ./simulator/

COPY --from=frontend-build \
    /build/frontend-react/dist \
    ./frontend_dist

ENV FRONTEND_DIST_DIR=/app/frontend_dist

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]