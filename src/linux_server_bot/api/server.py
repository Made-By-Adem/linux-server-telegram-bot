"""FastAPI application and uvicorn entrypoint."""

from __future__ import annotations

import logging
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from linux_server_bot.api.routes import router
from linux_server_bot.config import config, load_config
from linux_server_bot.shared.logging_setup import setup_logging
from linux_server_bot.shared.shell import warmup as shell_warmup
from linux_server_bot.shared.startup import (
    ensure_env,
    print_banner,
    setup_graceful_shutdown,
)

logger = logging.getLogger(__name__)


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

    # Ensure .env is configured (auto-generates API key if missing)
    env_path = os.path.join(os.getcwd(), ".env")
    ensure_env(env_path)

    # Graceful shutdown on SIGINT/SIGTERM
    setup_graceful_shutdown()

    config_path = os.environ.get("CONFIG_PATH", "config.yaml")
    load_config(config_path)

    setup_logging("api", config.log_directory)

    if not config.api.enabled:
        logger.info("API disabled in config")
        print("API disabled in config.yaml. The Telegram bot and monitoring continue to work without it.")
        return

    port = config.api.port
    logger.info("Starting Linux Server Bot API on port %d", port)

    # Startup banner
    print_banner("API", config)

    # Warm up shell detection + Docker CLI
    shell_warmup()

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
