"""Backup actions -- shared between bot and API."""

from __future__ import annotations

import logging
import shlex

from linux_server_bot.shared.shell import run_shell

logger = logging.getLogger(__name__)


def trigger_backup(script_path: str, target: str | None = None) -> dict:
    """Run the backup script, optionally with a single positional argument."""
    cmd = f"sudo {shlex.quote(script_path)}"
    if target:
        cmd += f" {shlex.quote(target)}"
    cmd += " 2>&1"
    logger.info("Triggering backup: %s", cmd)
    result = run_shell(cmd, timeout=600)
    return {"success": result.success, "output": result.stdout or result.stderr}


def get_backup_status() -> dict:
    """Get recent backup status from logs."""
    result = run_shell(
        "ls -lt /var/log/backup*.log 2>/dev/null | head -5;"
        " echo '---';"
        " tail -20 /var/log/backup*.log 2>/dev/null || echo 'No backup logs found.'"
    )
    return {"output": result.stdout.strip() or "No backup status available."}


def get_backup_size() -> dict:
    """Get backup disk usage."""
    result = run_shell(
        "du -sh /backup/ 2>/dev/null || du -sh /mnt/backup/ 2>/dev/null || echo 'Backup directory not found.'"
    )
    return {"output": result.stdout.strip()}
