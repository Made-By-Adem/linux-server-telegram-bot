"""Docker container actions -- shared between bot and API."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from linux_server_bot.shared.shell import run_command

logger = logging.getLogger(__name__)


@dataclass
class ContainerStatus:
    name: str
    status: str
    running: bool


def get_container_names() -> list[str]:
    """Dynamically fetch all container names from Docker."""
    result = run_command(["docker", "ps", "-a", "--format", "{{.Names}}"])
    if result.success and result.stdout.strip():
        return [n for n in result.stdout.strip().split("\n") if n]
    return []


def get_container_statuses() -> list[ContainerStatus]:
    """Get status of all containers with structured data."""
    result = run_command([
        "docker", "ps", "-a",
        "--format", "{{.Names}}\t{{.Status}}\t{{.State}}",
    ])
    containers: list[ContainerStatus] = []
    if result.success:
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                containers.append(ContainerStatus(
                    name=parts[0], status=parts[1], running=parts[2] == "running",
                ))
    return containers


def get_container_statuses_text() -> str:
    """Get formatted container status text for display."""
    result = run_command([
        "docker", "ps", "-a",
        "--format", "Name: {{.Names}}\nCreated at: {{.CreatedAt}}\nStatus: {{.Status}}\n",
    ])
    return result.stdout if result.success else f"Error: {result.stderr}"


def container_action(action: str, name: str) -> dict:
    """Perform a docker action (start/stop/restart) on a container."""
    logger.info("Docker %s: %s", action, name)
    result = run_command(["sudo", "docker", action, name])
    return {"name": name, "action": action, "success": result.success, "output": result.stdout, "error": result.stderr}


def container_action_all(action: str) -> list[dict]:
    """Perform a docker action on all containers."""
    results = []
    for name in get_container_names():
        results.append(container_action(action, name))
    if action == "stop":
        time.sleep(1)
    return results


def docker_cleanup() -> dict:
    """Run docker system prune."""
    result = run_command(["docker", "system", "prune", "-f"], timeout=60)
    return {"success": result.success, "output": result.stdout, "error": result.stderr}
