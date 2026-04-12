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

    config_path = os.environ.get("CONFIG_PATH", "config.yaml")
    load_config(config_path)

    setup_logging("api", config.log_directory)
    logger.info("Starting Linux Server Bot API on port %d", config.api.port)

    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=config.api.port, log_level="info")


if __name__ == "__main__":
    main()
