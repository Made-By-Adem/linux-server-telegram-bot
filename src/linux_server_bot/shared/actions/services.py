"""Systemd service actions -- shared between bot and API."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from linux_server_bot.shared.shell import run_command

logger = logging.getLogger(__name__)


@dataclass
class ServiceStatus:
    name: str
    state: str
    active: bool


def get_service_status(name: str) -> ServiceStatus:
    """Get the status of a single service."""
    result = run_command(["systemctl", "is-active", name])
    state = result.stdout.strip() or "unknown"
    return ServiceStatus(name=name, state=state, active=state == "active")


def get_service_statuses(services: list[str]) -> list[ServiceStatus]:
    """Get status of all configured services."""
    return [get_service_status(s) for s in services]


def service_action(action: str, name: str) -> dict:
    """Perform a systemctl action (start/stop/restart) on a service."""
    logger.info("Systemctl %s: %s", action, name)
    result = run_command(["sudo", "systemctl", action, name])
    return {"name": name, "action": action, "success": result.success, "output": result.stdout, "error": result.stderr}


def service_action_all(action: str, services: list[str]) -> list[dict]:
    """Perform a systemctl action on all configured services."""
    return [service_action(action, s) for s in services]
