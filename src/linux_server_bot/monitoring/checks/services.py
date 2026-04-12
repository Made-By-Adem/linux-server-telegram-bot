"""Service health monitoring with auto-restart."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.shared.shell import run_command

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)


def _is_service_running(service_name: str) -> bool:
    result = run_command(["systemctl", "is-active", service_name])
    return result.stdout.strip() == "active"


def _restart_service(service_name: str) -> bool:
    run_command(["sudo", "systemctl", "restart", service_name])
    return _is_service_running(service_name)


def check_services(bot: telebot.TeleBot, config: AppConfig) -> None:
    """Check all monitored services and auto-restart if down."""
    from linux_server_bot.shared.telegram import send_to_all

    for service in config.monitoring.services:
        logger.info("Checking service %s", service)
        if _is_service_running(service):
            logger.info("Service %s is running", service)
            continue

        logger.warning("Service %s is down, attempting restart", service)
        if _restart_service(service):
            logger.info("Service %s restarted successfully", service)
            send_to_all(
                bot, config,
                f"\U0001f9be \U0001f4e6 Service {service} was down, but I have restarted it.",
            )
        else:
            logger.error("Service %s could not be restarted", service)
            send_to_all(
                bot, config,
                f"\U0001f613 \U0001f4e6 Service {service} is down and I could not restart it!",
            )
