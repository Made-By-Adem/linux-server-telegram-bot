"""Systemd service actions -- shared between bot and API."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from linux_server_bot.shared.shell import run_command

logger = logging.getLogger(__name__)


def _normalize_service_name(name: str) -> str:
    """Normalize systemd unit name to a stable service key."""
    if name.endswith(".service"):
        return name[: -len(".service")]
    return name


@dataclass
class ServiceStatus:
    name: str
    state: str
    active: bool


def get_enabled_service_names() -> list[str]:
    """Auto-detect all enabled systemd services.

    Returns service names (without .service suffix) for all services that
    are set to start on boot.  These are the services a user would expect
    to be running at all times.
    """
    result = run_command(
        [
            "systemctl",
            "list-unit-files",
            "--type=service",
            "--state=enabled",
            "--no-legend",
            "--no-pager",
        ]
    )
    names: list[str] = []
    if result.success:
        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if parts:
                name = parts[0]
                names.append(_normalize_service_name(name))
    names.sort()
    return names


def get_service_status(name: str) -> ServiceStatus:
    """Get the status of a single service."""
    norm_name = _normalize_service_name(name)

    result = run_command(["systemctl", "is-active", norm_name])
    state = result.stdout.strip()

    if not state and not norm_name.endswith(".service"):
        retry = run_command(["systemctl", "is-active", f"{norm_name}.service"])
        if retry.stdout.strip():
            result = retry
            state = retry.stdout.strip()

    if not state:
        state = result.stderr.strip() or "unknown"

    return ServiceStatus(name=norm_name, state=state, active=state == "active")


def get_service_statuses(services: list[str]) -> list[ServiceStatus]:
    """Get status of all configured services."""
    normalized = sorted({_normalize_service_name(s) for s in services})
    return [get_service_status(s) for s in normalized]


def service_action(action: str, name: str) -> dict:
    """Perform a systemctl action (start/stop/restart) on a service."""
    norm_name = _normalize_service_name(name)
    logger.info("Systemctl %s: %s", action, norm_name)
    result = run_command(["sudo", "systemctl", action, norm_name])
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
