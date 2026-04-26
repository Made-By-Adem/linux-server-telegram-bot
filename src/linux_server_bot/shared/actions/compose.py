"""Docker Compose stack actions -- shared between bot and API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.shared.shell import run_command

if TYPE_CHECKING:
    from linux_server_bot.config import ComposeStack

logger = logging.getLogger(__name__)

# Order matters: compose v2 prefers .yaml, but .yml is still common.
_COMPOSE_FILENAMES = ("docker-compose.yaml", "docker-compose.yml", "compose.yaml", "compose.yml")


def _looks_like_missing_compose_v2(result) -> bool:
    """Detect cases where ``docker compose`` is unavailable/incompatible."""
    error_text = (result.stderr or "").lower()
    return "unknown shorthand flag: 'f' in -f" in error_text or "'compose' is not a docker command" in error_text


def _compose_file(path: str) -> str:
    """Return ``"<path>/<filename>"`` for the first compose file that exists.

    Probes for the standard names via ``ls`` on the host (so it works the
    same whether the bot runs in Docker or natively). Falls back to the
    canonical ``docker-compose.yaml`` so error messages stay informative.
    """
    probe = run_command(["ls"] + [f"{path}/{name}" for name in _COMPOSE_FILENAMES], force_host=True)
    for line in probe.stdout.splitlines():
        line = line.strip()
        if line.startswith(path + "/"):
            return line
    return f"{path}/docker-compose.yaml"


def _compose_cmd(path: str, args: list[str], timeout: int = 120):
    """Run ``docker compose -f <stack>/<file> <args>`` against the host.

    The compose file lives on the host filesystem and is rarely mounted
    into the bot container, so the call is forced through nsenter to
    enter the host's mount namespace. The host's docker CLI talks to
    the same daemon via the shared docker socket either way.
    """
    compose_file = _compose_file(path)
    result = run_command(
        ["docker", "compose", "-f", compose_file] + args,
        timeout=timeout,
        force_host=True,
    )
    if not result.success and _looks_like_missing_compose_v2(result):
        result.stderr = (
            "Docker Compose v2 is not available on this host. "
            "Install/enable the Docker Compose plugin so 'docker compose' works."
        )
    return result


def get_stack_status(stack: ComposeStack) -> dict:
    """Get status of a compose stack."""
    result = _compose_cmd(stack.path, ["ps", "--format", "table {{.Name}}\t{{.Status}}"])
    return {
        "name": stack.name,
        "path": stack.path,
        "success": result.success,
        "output": result.stdout.strip() if result.success else result.stderr,
    }


def stack_up(stack: ComposeStack) -> dict:
    """Bring a compose stack up."""
    logger.info("Compose up: %s", stack.name)
    result = _compose_cmd(stack.path, ["up", "-d"])
    return {"name": stack.name, "success": result.success, "output": result.stdout, "error": result.stderr}


def stack_down(stack: ComposeStack) -> dict:
    """Bring a compose stack down."""
    logger.info("Compose down: %s", stack.name)
    result = _compose_cmd(stack.path, ["down"])
    return {"name": stack.name, "success": result.success, "output": result.stdout, "error": result.stderr}


def stack_restart(stack: ComposeStack) -> dict:
    """Restart a compose stack."""
    logger.info("Compose restart: %s", stack.name)
    result = _compose_cmd(stack.path, ["restart"])
    return {"name": stack.name, "success": result.success, "output": result.stdout, "error": result.stderr}


def stack_pull_recreate(stack: ComposeStack) -> dict:
    """Pull images and recreate a compose stack."""
    logger.info("Compose pull+recreate: %s", stack.name)
    pull = _compose_cmd(stack.path, ["pull"], timeout=300)
    if not pull.success:
        return {"name": stack.name, "success": False, "error": f"Pull failed: {pull.stderr}"}
    up = _compose_cmd(stack.path, ["up", "-d", "--force-recreate"])
    return {"name": stack.name, "success": up.success, "output": up.stdout, "error": up.stderr}


def stack_logs(stack: ComposeStack, tail: int = 50) -> dict:
    """Get logs from a compose stack."""
    result = _compose_cmd(stack.path, ["logs", "--tail", str(tail)])
    return {"name": stack.name, "output": result.stdout or result.stderr}
