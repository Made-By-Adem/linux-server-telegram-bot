"""Docker container health monitoring with auto-restart."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from linux_server_bot.shared.shell import run_command

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)


def _is_container_running(container_name: str) -> bool:
    result = run_command(["docker", "inspect", "--format", "{{.State.Status}}", container_name])
    return result.stdout.strip() == "running"


def _restart_container(container_name: str) -> bool:
    run_command(["docker", "start", container_name])
    time.sleep(5)
    return _is_container_running(container_name)


def check_containers(bot: telebot.TeleBot, config: AppConfig) -> None:
    """Check all monitored containers, respecting per-container on_failure policy."""
    from linux_server_bot.shared.telegram import send_to_all

    for item in config.monitoring.containers:
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
                bot, config,
                f"\u26a0\ufe0f \U0001f433 Container <b>{container}</b> is down.",
            )
            continue

        # policy == "notify_restart" (default)
        logger.warning("Container %s is down, attempting restart", container)
        if _restart_container(container):
            logger.info("Container %s restarted successfully", container)
            send_to_all(
                bot, config,
                f"\U0001f9be \U0001f433 Container <b>{container}</b> was down, but I have restarted it.",
            )
        else:
            logger.error("Container %s could not be restarted", container)
            send_to_all(
                bot, config,
                f"\U0001f613 \U0001f433 Container <b>{container}</b> is down and I could not restart it!",
            )
