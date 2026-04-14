"""Systemd service actions -- shared between bot and API."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from linux_server_bot.shared.shell import run_command

logger = logging.getLogger(__name__)

# Short-lived cache so pre-warm results survive until the first user tap.
_CACHE_TTL = 30  # seconds
_status_cache: dict | None = None  # {tuple(service_names): list[ServiceStatus]}
_status_cache_time: float = 0.0
_status_cache_lock = threading.Lock()


def _normalize_service_name(name: str) -> str:
    """Normalize systemd unit name to a stable service key."""
    if name.endswith(".service"):
        return name[: -len(".service")]
    return name


def _should_retry_with_sudo(result) -> bool:
    text = f"{result.stdout}\n{result.stderr}".lower()
    return (
        "failed to connect to bus" in text or "access denied" in text or "interactive authentication required" in text
    )


def _run_systemctl(args: list[str], timeout: int = 30):
    """Run systemctl and retry with sudo when dbus/policy blocks access."""
    result = run_command(["systemctl"] + args, timeout=timeout)
    if result.success or not _should_retry_with_sudo(result):
        return result
    logger.warning("Retrying systemctl with sudo due to bus/permission error")
    return run_command(["sudo", "systemctl"] + args, timeout=timeout)


def _parse_service_names_from_systemctl(text: str) -> list[str]:
    names: set[str] = set()
    for line in text.strip().splitlines():
        parts = line.split()
        if not parts:
            continue
        first = parts[0]
        if first.endswith(".service"):
            names.add(_normalize_service_name(first))
    return sorted(names)


@dataclass
class ServiceStatus:
    name: str
    state: str
    active: bool


def get_enabled_service_names() -> list[str]:
    """Auto-detect live services, with enabled-services fallback.

    Prefers currently running services. If that detection returns nothing,
    falls back to enabled services.
    """
    live = _run_systemctl(
        [
            "list-units",
            "--type=service",
            "--state=running",
            "--no-legend",
            "--no-pager",
            "--plain",
        ]
    )
    live_names = _parse_service_names_from_systemctl(live.stdout) if live.success else []
    if live_names:
        return live_names

    enabled = _run_systemctl(
        [
            "list-unit-files",
            "--type=service",
            "--state=enabled",
            "--no-legend",
            "--no-pager",
        ]
    )
    if enabled.success:
        return _parse_service_names_from_systemctl(enabled.stdout)

    return []


def get_service_status(name: str) -> ServiceStatus:
    """Get the status of a single service."""
    norm_name = _normalize_service_name(name)

    result = _run_systemctl(["is-active", norm_name])
    state = result.stdout.strip()

    if not state and not norm_name.endswith(".service"):
        retry = _run_systemctl(["is-active", f"{norm_name}.service"])
        if retry.stdout.strip():
            result = retry
            state = retry.stdout.strip()

    if not state:
        state = result.stderr.strip() or "unknown"

    return ServiceStatus(name=norm_name, state=state, active=state == "active")


def invalidate_status_cache() -> None:
    """Clear the service status cache (call after start/stop/restart)."""
    global _status_cache, _status_cache_time
    with _status_cache_lock:
        _status_cache = None
        _status_cache_time = 0.0


def get_service_statuses(services: list[str]) -> list[ServiceStatus]:
    """Get status of all configured services.

    Results are cached for up to ``_CACHE_TTL`` seconds so that the pre-warm
    at startup can serve the first user tap instantly.
    """
    global _status_cache, _status_cache_time

    normalized = sorted({_normalize_service_name(s) for s in services})
    cache_key = tuple(normalized)

    with _status_cache_lock:
        if (
            _status_cache is not None
            and _status_cache.get("key") == cache_key
            and (time.time() - _status_cache_time) < _CACHE_TTL
        ):
            return list(_status_cache["data"])

    result = [get_service_status(s) for s in normalized]

    with _status_cache_lock:
        _status_cache = {"key": cache_key, "data": list(result)}
        _status_cache_time = time.time()

    return result


def service_action(action: str, name: str) -> dict:
    """Perform a systemctl action (start/stop/restart) on a service."""
    norm_name = _normalize_service_name(name)
    logger.info("Systemctl %s: %s", action, norm_name)
    result = _run_systemctl([action, norm_name])
    invalidate_status_cache()
    return {
        "name": norm_name,
        "action": action,
        "success": result.success,
        "output": result.stdout,
        "error": result.stderr,
    }


def service_action_all(action: str, services: list[str]) -> list[dict]:
    """Perform a systemctl action on all configured services."""
    return [service_action(action, s) for s in services]
