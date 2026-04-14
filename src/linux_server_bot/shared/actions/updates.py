"""Container update actions -- shared between bot and API."""

from __future__ import annotations

import logging

from linux_server_bot.shared.shell import run_command

logger = logging.getLogger(__name__)


def dry_run_updates(script_path: str) -> dict:
    """Run container updates in dry-run mode."""
    logger.info("Update dry-run: %s", script_path)
    result = run_command(["sudo", script_path, "--dry-run"], timeout=300)
    return {"success": result.success, "output": result.stdout or result.stderr}


def trigger_updates(script_path: str) -> dict:
    """Run container updates."""
    logger.info("Triggering updates: %s", script_path)
    result = run_command(["sudo", script_path], timeout=600)
    return {"success": result.success, "output": result.stdout or result.stderr}


def rollback_updates(script_path: str) -> dict:
    """Rollback last container update."""
    logger.info("Rolling back updates: %s", script_path)
    result = run_command(["sudo", script_path, "--rollback"], timeout=300)
    return {"success": result.success, "output": result.stdout or result.stderr}
