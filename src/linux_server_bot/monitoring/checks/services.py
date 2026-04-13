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
    status = result.stdout.strip()
    # If systemctl itself failed (e.g. no systemd access), don't treat as "down"
    if not result.success and not status:
        logger.warning(
            "systemctl failed for %s (rc=%d): %s",
            service_name,
            result.returncode,
            result.stderr.strip()[:200],
        )
        return True  # Assume running if we can't check
    return status == "active"


def _restart_service(service_name: str) -> bool:
    run_command(["sudo", "systemctl", "restart", service_name])
    return _is_service_running(service_name)


def check_services(bot: telebot.TeleBot, config: AppConfig) -> None:
    """Check services listed in ``config.services``.

    Only services explicitly configured are checked. The on_failure
    policy on each item determines the action taken when a service is down.
    """
    from linux_server_bot.shared.telegram import send_to_all

    if not config.services:
        logger.info("No services configured for monitoring")
        return

    for item in config.services:
        service = item.name
        policy = item.on_failure
        logger.info("Checking service %s (policy: %s)", service, policy)

        if _is_service_running(service):
            logger.info("Service %s is running", service)
            continue

        if policy == "ignore":
            logger.info("Service %s is down, but policy is 'ignore' -- skipping", service)
            continue

        if policy == "notify":
            logger.warning("Service %s is down (notify only)", service)
            send_to_all(
                bot,
                config,
                f"\u26a0\ufe0f \U0001f4e6 Service <b>{service}</b> is down.",
            )
            continue

        # policy == "notify_restart"
        logger.warning("Service %s is down, attempting restart", service)
        if _restart_service(service):
            logger.info("Service %s restarted successfully", service)
            send_to_all(
                bot,
                config,
                f"\U0001f9be \U0001f4e6 Service <b>{service}</b> was down, but I have restarted it.",
            )
        else:
            logger.error("Service %s could not be restarted", service)
            send_to_all(
                bot,
                config,
                f"\U0001f613 \U0001f4e6 Service <b>{service}</b> is down and I could not restart it!",
            )
