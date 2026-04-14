"""Docker container health monitoring with auto-restart."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from linux_server_bot.shared.actions.docker import (
    container_action,
    get_container_statuses,
    resolve_container_patterns,
)

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)


def _is_container_running(container_name: str) -> bool:
    statuses = get_container_statuses()
    for s in statuses:
        if s.name == container_name:
            return s.running
    return False


def _restart_container(container_name: str) -> bool:
    result = container_action("start", container_name)
    if not result["success"]:
        return False
    time.sleep(5)
    return _is_container_running(container_name)


def check_containers(bot: telebot.TeleBot, config: AppConfig) -> None:
    """Check containers listed in ``config.containers``.

    Only containers explicitly configured are checked. The on_failure
    policy on each item determines the action taken when a container is down.
    """
    from linux_server_bot.shared.telegram import send_to_all

    if not config.containers:
        logger.info("No containers configured for monitoring")
        return

    resolved = resolve_container_patterns(config.containers)
    for item in resolved:
        container = item.name
        policy = item.on_failure
        logger.info("Checking container %s (policy: %s)", container, policy)

        if _is_container_running(container):
            logger.info("Container %s is running", container)
            continue

        if policy == "ignore":
            logger.info("Container %s is down, but policy is 'ignore' -- skipping", container)
            continue

        if policy == "notify":
            logger.warning("Container %s is down (notify only)", container)
            send_to_all(
                bot,
                config,
                f"\u26a0\ufe0f \U0001f433 Container <b>{container}</b> is down.",
            )
            continue

        # policy == "notify_restart"
        logger.warning("Container %s is down, attempting restart", container)
        if _restart_container(container):
            logger.info("Container %s restarted successfully", container)
            send_to_all(
                bot,
                config,
                f"\U0001f9be \U0001f433 Container <b>{container}</b> was down, but I have restarted it.",
            )
        else:
            logger.error("Container %s could not be restarted", container)
            send_to_all(
                bot,
                config,
                f"\U0001f613 \U0001f433 Container <b>{container}</b> is down and I could not restart it!",
            )
