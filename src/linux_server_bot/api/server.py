"""FastAPI application and uvicorn entrypoint."""

from __future__ import annotations

import logging
import os
import secrets
import socket

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from linux_server_bot.api.routes import router
from linux_server_bot.config import config, load_config
from linux_server_bot.shared.logging_setup import setup_logging

logger = logging.getLogger(__name__)

_PLACEHOLDER_KEYS = {
    "",
    "your-secret-api-key-here",
    "your-api-key-here",
    "changeme",
}


def _ensure_api_key() -> None:
    """Generate an API key and write it to .env if missing or placeholder."""
    current = os.environ.get("API_KEY", "").strip()
    if current and current not in _PLACEHOLDER_KEYS:
        return

    new_key = secrets.token_urlsafe(32)
    os.environ["API_KEY"] = new_key

    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            content = f.read()
        # Replace existing placeholder line
        replaced = False
        lines = content.splitlines(keepends=True)
        for i, line in enumerate(lines):
            stripped = line.split("#")[0].strip()
            if stripped.startswith("API_KEY="):
                lines[i] = f"API_KEY={new_key}\n"
                replaced = True
                break
        if not replaced:
            lines.append(f"\nAPI_KEY={new_key}\n")
        with open(env_path, "w") as f:
            f.writelines(lines)
    else:
        with open(env_path, "w") as f:
            f.write(f"API_KEY={new_key}\n")

    logger.info("Generated new API key and saved to .env")


def _check_port(port: int) -> None:
    """Check if a port is available. Exit with a clear error if not."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            logger.error(
                "Port %d is already in use. Check what's using it with: "
                "sudo lsof -i :%d",
                port,
                port,
            )
            raise SystemExit(1)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Linux Server Bot API",
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    @app.get("/api/health")
    async def health():
        return {"status": "healthy", "version": "2.0.0"}

    app.include_router(router)
    return app


def main() -> None:
    """Main entry point for the API server."""
    load_dotenv()
    _ensure_api_key()

    config_path = os.environ.get("CONFIG_PATH", "config.yaml")
    load_config(config_path)

    setup_logging("api", config.log_directory)
    logger.info("Starting Linux Server Bot API on port %d", config.api.port)

    _check_port(config.api.port)

    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=config.api.port, log_level="info")


if __name__ == "__main__":
    main()
