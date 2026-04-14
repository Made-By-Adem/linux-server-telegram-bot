"""System resource monitoring: CPU, temperature, storage."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from linux_server_bot.shared.shell import run_shell
from linux_server_bot.shared.telegram import escape_html

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)


def _get_cpu_usage() -> float | None:
    """Get total CPU usage percentage (100 - idle) from top."""
    result = run_shell("top -bn 1 | awk '/^%Cpu/ {printf \"%.1f\", 100 - $8}'")
    try:
        return float(result.stdout.strip())
    except (ValueError, IndexError):
        logger.warning("Could not parse CPU usage: %s", result.stdout)
        return None


def check_cpu(bot: telebot.TeleBot, config: AppConfig) -> None:
    """Check CPU usage with double-verification on high load."""
    from linux_server_bot.shared.telegram import send_to_all

    threshold = config.monitoring.thresholds.get("cpu_percent", 80)
    usage = _get_cpu_usage()
    if usage is None:
        return

    logger.info("CPU usage: %.1f%%", usage)
    if usage <= threshold:
        return

    # Double-check after 5 seconds
    time.sleep(5)
    usage2 = _get_cpu_usage()
    if usage2 is None or usage2 <= threshold:
        return

    # Get top consumers
    top_result = run_shell("ps -eo pid,%cpu,%mem,comm --sort=-%cpu | head -n 11")
    consumers = escape_html(top_result.stdout)
    logger.warning("CPU usage sustained at %.1f%%", usage2)
    send_to_all(
        bot,
        config,
        f"\U0001f525 CPU usage is high (>{threshold}%). "
        f"First: {usage:.1f}%, after 5s: {usage2:.1f}%.\n"
        f"Top consumers:\n<pre>{consumers}</pre>",
        parse_mode="HTML",
    )


def check_temperature(bot: telebot.TeleBot, config: AppConfig) -> None:
    """Check system temperature and report fan state if high."""
    from linux_server_bot.shared.telegram import send_to_all

    threshold = config.monitoring.thresholds.get("temperature_celsius", 50)
    result = run_shell("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
    try:
        temp_c = int(result.stdout.strip()) / 1000
    except (ValueError, IndexError):
        logger.warning("Could not read temperature")
        return

    logger.info("Temperature: %.1f C", temp_c)
    if temp_c <= threshold:
        return

    # Read fan state
    fan_result = run_shell("cat /sys/class/thermal/cooling_device0/cur_state 2>/dev/null")
    fan_state = fan_result.stdout.strip() or "unknown"

    if fan_state == "1":
        send_to_all(
            bot,
            config,
            f"\U0001f321\ufe0f Temperature is high (>{threshold}\u00b0C). "
            f"Current: {temp_c:.1f}\u00b0C. Fans are ON (state: {fan_state}).",
        )
    else:
        send_to_all(
            bot,
            config,
            f"\U0001f321\ufe0f Temperature is high (>{threshold}\u00b0C). "
            f"Current: {temp_c:.1f}\u00b0C. Fans are NOT on (state: {fan_state}).",
        )


def check_storage(bot: telebot.TeleBot, config: AppConfig) -> None:
    """Check root partition storage usage."""
    from linux_server_bot.shared.telegram import send_to_all

    threshold = config.monitoring.thresholds.get("storage_percent", 90)
    result = run_shell("df -h / | awk 'NR==2{print $5}'")
    try:
        usage = int(result.stdout.strip().rstrip("%"))
    except (ValueError, IndexError):
        logger.warning("Could not parse storage usage")
        return

    logger.info("Storage usage: %d%%", usage)
    if usage > threshold:
        send_to_all(bot, config, f"\U0001f4be Storage usage is high ({usage}% > {threshold}%).")
