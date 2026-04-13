FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-traditional \
    etherwake \
    stress-ng \
    dbus \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 botuser && \
    useradd --uid 1000 --gid botuser --create-home botuser

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir . && \
    mkdir -p /app/logs && chown -R botuser:botuser /app

USER botuser

VOLUME ["/app/logs"]

CMD ["linux-bot"]
