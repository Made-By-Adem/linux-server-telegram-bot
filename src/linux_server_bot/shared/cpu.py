"""Shared CPU usage helper used by both sysinfo actions and monitoring checks."""

from __future__ import annotations

import logging
import time

from linux_server_bot.shared.shell import run_command

logger = logging.getLogger(__name__)


def _read_cpu_times() -> tuple[int, int] | None:
    """Read aggregate CPU jiffies from /proc/stat. Returns (total, idle) or None.

    Idle is just the ``idle`` column (index 3), not iowait, so iowait-heavy
    workloads still count toward usage/alert thresholds.
    """
    result = run_command(["head", "-n", "1", "/proc/stat"])
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


def read_cpu_percent(sample_interval: float = 1.0) -> float | None:
    """Return CPU usage % measured over *sample_interval* seconds, or None on error."""
    first = _read_cpu_times()
    if first is None:
        logger.warning("Could not read /proc/stat (first sample)")
        return None
    time.sleep(sample_interval)
    second = _read_cpu_times()
    if second is None:
        logger.warning("Could not read /proc/stat (second sample)")
        return None
    total_delta = second[0] - first[0]
    idle_delta = second[1] - first[1]
    if total_delta <= 0:
        logger.warning("Invalid /proc/stat delta: total=%d idle=%d", total_delta, idle_delta)
        return None
    return round(100.0 * (1.0 - idle_delta / total_delta), 1)
