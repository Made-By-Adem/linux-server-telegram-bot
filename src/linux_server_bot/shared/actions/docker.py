"""Docker container actions -- shared between bot and API."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from linux_server_bot.shared.shell import run_command

logger = logging.getLogger(__name__)


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


def get_container_statuses() -> list[ContainerStatus]:
    """Get status of all containers with structured data."""
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
    result = _run_docker(["system", "prune", "-f"], timeout=60)
    return {"success": result.success, "output": result.stdout, "error": result.stderr}
