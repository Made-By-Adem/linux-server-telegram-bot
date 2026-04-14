"""Monitoring entrypoint -- scheduler that runs health checks periodically."""

from __future__ import annotations

import logging
import os
import time

import schedule
from dotenv import load_dotenv

from linux_server_bot.config import config, load_config
from linux_server_bot.monitoring.checks import containers, security, servers, services, system
from linux_server_bot.shared.logging_setup import setup_logging
from linux_server_bot.shared.shell import warmup as shell_warmup
from linux_server_bot.shared.startup import (
    ensure_env,
    print_banner,
    run_preflight_checks,
    setup_graceful_shutdown,
)
from linux_server_bot.shared.telegram import create_bot

logger = logging.getLogger(__name__)


def _write_health_check():
    """Write a health check file for Docker HEALTHCHECK."""
    try:
        with open("/tmp/monitor_healthy", "w") as f:
            f.write(str(time.time()))
    except OSError:
        pass


def _run_checks(bot) -> None:
    """Execute all monitoring checks."""
    logger.info("Starting monitoring cycle...")

    services.check_services(bot, config)
    containers.check_containers(bot, config)
    servers.check_servers(bot, config)
    system.check_cpu(bot, config)
    system.check_temperature(bot, config)
    system.check_storage(bot, config)
    security.check_failed_logins(bot, config)
    security.check_banned_ips(bot, config)

    _write_health_check()
    logger.info("Monitoring cycle finished.")


def main() -> None:
    """Main entry point for the monitoring service."""
    load_dotenv(override=True)

    # Ensure .env is configured
    env_path = os.path.join(os.getcwd(), ".env")
    ensure_env(env_path)

    # Graceful shutdown on SIGINT/SIGTERM
    setup_graceful_shutdown()

    config_path = os.environ.get("CONFIG_PATH", "config.yaml")
    load_config(config_path)

    setup_logging("monitoring", config.log_directory)
    logger.info("Starting Linux Server Monitor v2.0.0")

    # Preflight checks
    checks = run_preflight_checks(config_path, config.bot_token)
    if not checks["bot_token"]:
        logger.error("Cannot start monitoring without a valid bot token. Exiting.")
        raise SystemExit(1)

    # Startup banner
    print_banner("Monitoring", config)

    # Warm up shell detection + Docker CLI
    shell_warmup()

    bot = create_bot(config.bot_token)

    # Run immediately on startup
    _run_checks(bot)

    # Schedule periodic runs
    interval = config.monitoring.interval_minutes
    schedule.every(interval).minutes.do(_run_checks, bot)
    logger.info("Scheduled monitoring every %d minutes", interval)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
