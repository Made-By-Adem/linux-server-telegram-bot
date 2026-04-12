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


def _is_port_free(port: int) -> bool:
    """Check if a port is available on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _find_free_port(preferred: int, max_attempts: int = 20) -> int | None:
    """Return *preferred* if free, otherwise try the next ports.

    After *max_attempts* failures, ask the user for a port interactively.
    Returns ``None`` if the user chooses to skip the API.
    """
    for offset in range(max_attempts):
        candidate = preferred + offset
        if _is_port_free(candidate):
            if offset > 0:
                logger.warning(
                    "Port %d is in use, using %d instead",
                    preferred,
                    candidate,
                )
            return candidate

    # All automatic attempts exhausted — ask the user
    print(
        f"\nPorts {preferred}-{preferred + max_attempts - 1} are all in use."
    )
    try:
        answer = input(
            "Enter a port number to use, or press Enter to skip the API: "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        # Non-interactive environment (e.g. Docker) — skip
        return None

    if not answer:
        return None

    try:
        port = int(answer)
    except ValueError:
        print(f"'{answer}' is not a valid port number. Skipping API.")
        return None

    if _is_port_free(port):
        return port

    print(f"Port {port} is also in use. Skipping API.")
    return None


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

    port = _find_free_port(config.api.port)
    if port is None:
        logger.info("API skipped — no free port available")
        print("API disabled. The Telegram bot and monitoring continue to work without it.")
        return

    logger.info("Starting Linux Server Bot API on port %d", port)

    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
