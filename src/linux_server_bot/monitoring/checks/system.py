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


def _read_cpu_times() -> tuple[int, int] | None:
    """Read aggregate CPU jiffies from /proc/stat. Returns (total, idle) or None.

    Idle is just the ``idle`` column, matching ``top``'s ``id`` field
    (``$8`` in the previous awk parse) -- iowait is NOT treated as idle, so
    iowait-heavy workloads still count toward the alert threshold.
    """
    result = run_shell("head -n 1 /proc/stat")
    if not result.success:
        return None
    parts = result.stdout.split()
    if len(parts) < 5 or parts[0] != "cpu":
        return None
    try:
        fields = [int(x) for x in parts[1:]]
    except ValueError:
        return None
    idle = fields[3]
    total = sum(fields)
    return total, idle


def _get_cpu_usage() -> float | None:
    """Get total CPU usage percentage from /proc/stat over a 1-second window.

    Replaces the previous ``top -bn 1 | awk`` parsing which mis-read idle as 0
    whenever any %Cpu(s) field reached 100.0 (top's fixed-width column shifts
    by one when the leading space disappears, so awk's $8 became "ni," instead
    of the idle value).
    """
    first = _read_cpu_times()
    if first is None:
        logger.warning("Could not read /proc/stat (first sample)")
        return None
    time.sleep(1)
    second = _read_cpu_times()
    if second is None:
        logger.warning("Could not read /proc/stat (second sample)")
        return None
    total_delta = second[0] - first[0]
    idle_delta = second[1] - first[1]
    if total_delta <= 0:
        logger.warning(
            "Invalid /proc/stat delta: total=%d idle=%d", total_delta, idle_delta
        )
        return None
    return round(100.0 * (1.0 - idle_delta / total_delta), 1)


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

    delay = int(config.monitoring.thresholds.get("recheck_delay_seconds", 5))
    time.sleep(delay)
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
        f"First: {usage:.1f}%, after {delay}s: {usage2:.1f}%.\n"
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
