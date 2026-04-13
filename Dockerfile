FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-traditional \
    etherwake \
    stress-ng \
    dbus \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir . && \
    mkdir -p /app/logs

VOLUME ["/app/logs"]

CMD ["linux-bot"]
