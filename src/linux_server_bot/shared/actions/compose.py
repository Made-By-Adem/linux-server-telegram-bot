"""Docker Compose stack actions -- shared between bot and API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.shared.shell import run_command

if TYPE_CHECKING:
    from linux_server_bot.config import ComposeStack

logger = logging.getLogger(__name__)


def _compose_cmd(path: str, args: list[str], timeout: int = 120):
    return run_command(
        ["docker", "compose", "-f", f"{path}/docker-compose.yml"] + args,
        timeout=timeout,
    )


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
