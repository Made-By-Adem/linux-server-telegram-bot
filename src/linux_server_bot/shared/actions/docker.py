"""Docker container actions -- shared between bot and API."""

from __future__ import annotations

import fnmatch
import logging
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from linux_server_bot.shared.shell import run_command

if TYPE_CHECKING:
    from linux_server_bot.config import MonitoredItem

logger = logging.getLogger(__name__)

# Short-lived cache so pre-warm results survive until the first user tap.
_CACHE_TTL = 30  # seconds
_status_cache: list | None = None
_status_cache_time: float = 0.0
_status_cache_lock = threading.Lock()


def _should_retry_with_sudo(result) -> bool:
    error_text = (result.stderr or "").lower()
    return "permission denied" in error_text and "docker daemon socket" in error_text


def _run_docker(args: list[str], timeout: int = 30):
    """Run docker command and retry with sudo on daemon-socket permission errors."""
    result = run_command(["docker"] + args, timeout=timeout)
    if result.success or not _should_retry_with_sudo(result):
        return result
    logger.warning("Retrying docker command with sudo due to socket permission error")
    return run_command(["sudo", "docker"] + args, timeout=timeout)


@dataclass
class ContainerStatus:
    name: str
    status: str
    running: bool


def get_container_names() -> list[str]:
    """Dynamically fetch all container names from Docker."""
    result = _run_docker(["ps", "-a", "--format", "{{.Names}}"])
    if result.success and result.stdout.strip():
        return [n for n in result.stdout.strip().split("\n") if n]
    return []


def _is_pattern(name: str) -> bool:
    """Check if a container name contains glob wildcard characters."""
    return any(c in name for c in ("*", "?", "["))


def resolve_container_patterns(items: list[MonitoredItem]) -> list[MonitoredItem]:
    """Expand wildcard patterns in monitored items against actual Docker containers.

    Items with names containing ``*``, ``?``, or ``[`` are treated as glob
    patterns (fnmatch) and matched against all container names from
    ``docker ps -a``.  Non-pattern items are passed through as-is.

    Returns a new list of ``MonitoredItem`` objects with concrete container
    names.  Duplicate names are suppressed (first match wins).
    """
    from linux_server_bot.config import MonitoredItem as MI

    has_patterns = any(_is_pattern(item.name) for item in items)
    if not has_patterns:
        return list(items)

    all_names = get_container_names()
    result: list[MonitoredItem] = []
    seen: set[str] = set()

    for item in items:
        if _is_pattern(item.name):
            for name in all_names:
                if fnmatch.fnmatch(name, item.name) and name not in seen:
                    result.append(MI(name=name, on_failure=item.on_failure))
                    seen.add(name)
        else:
            if item.name not in seen:
                result.append(item)
                seen.add(item.name)

    return result


def invalidate_status_cache() -> None:
    """Clear the container status cache (call after start/stop/restart)."""
    global _status_cache, _status_cache_time
    with _status_cache_lock:
        _status_cache = None
        _status_cache_time = 0.0


def get_container_statuses() -> list[ContainerStatus]:
    """Get status of all containers with structured data.

    Results are cached for up to ``_CACHE_TTL`` seconds so that the pre-warm
    at startup can serve the first user tap instantly.
    """
    global _status_cache, _status_cache_time

    with _status_cache_lock:
        if _status_cache is not None and (time.time() - _status_cache_time) < _CACHE_TTL:
            logger.debug("get_container_statuses: CACHE HIT (age=%.1fs)", time.time() - _status_cache_time)
            return list(_status_cache)

    logger.debug("get_container_statuses: CACHE MISS, running docker ps")
    result = _run_docker(["ps", "-a", "--format", "{{.Names}}\t{{.Status}}\t{{.State}}"])
    containers: list[ContainerStatus] = []
    if result.success:
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                containers.append(
                    ContainerStatus(
                        name=parts[0],
                        status=parts[1],
                        running=parts[2] == "running",
                    )
                )

    with _status_cache_lock:
        _status_cache = list(containers)
        _status_cache_time = time.time()

    return containers


def get_container_statuses_text() -> str:
    """Get formatted container status text for display."""
    result = _run_docker(
        [
            "ps",
            "-a",
            "--format",
            "Name: {{.Names}}\nCreated at: {{.CreatedAt}}\nStatus: {{.Status}}\n",
        ]
    )
    return result.stdout if result.success else f"Error: {result.stderr}"


def container_action(action: str, name: str) -> dict:
    """Perform a docker action (start/stop/restart) on a container."""
    logger.info("Docker %s: %s", action, name)
    result = _run_docker([action, name])
    invalidate_status_cache()
    return {"name": name, "action": action, "success": result.success, "output": result.stdout, "error": result.stderr}


def container_action_all(action: str, names: list[str] | None = None) -> list[dict]:
    """Perform a docker action on the given containers (or all if not specified)."""
    if names is None:
        names = get_container_names()
    results = []
    for name in names:
        results.append(container_action(action, name))
    if action == "stop":
        time.sleep(1)
    return results


def docker_cleanup() -> dict:
    """Run docker system prune."""
    result = _run_docker(["system", "prune", "-f"], timeout=60)
    return {"success": result.success, "output": result.stdout, "error": result.stderr}
