FROM node:22-bookworm-slim AS web-builder

WORKDIR /web

COPY src/web/package.json src/web/package-lock.json ./
RUN npm ci

COPY src/web ./
ENV AI4MS_STATIC_EXPORT=1
RUN npm run build


FROM python:3.12-slim AS python-builder

WORKDIR /build

COPY pyproject.toml LICENSE ./
COPY src ./src

RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels .


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AI4MS_HOST=0.0.0.0 \
    AI4MS_PORT=8000 \
    AI4MS_DATA_DIR=/app/data \
    AI4MS_WEB_ROOT=/app/web

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY --from=python-builder /wheels/riffband-*.whl /tmp/
RUN pip install --no-cache-dir /tmp/riffband-*.whl \
    && rm -f /tmp/riffband-*.whl
COPY --from=web-builder /web/out ./web

RUN mkdir -p /app/data
VOLUME ["/app/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"

CMD ["uvicorn", "ai4ms.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
