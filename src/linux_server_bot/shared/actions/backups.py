"""Backup actions -- shared between bot and API."""

from __future__ import annotations

import logging

from linux_server_bot.shared.shell import run_shell

logger = logging.getLogger(__name__)


def trigger_backup(script_path: str) -> dict:
    """Run the backup script."""
    logger.info("Triggering backup: %s", script_path)
    result = run_shell(f"sudo {script_path} 2>&1", timeout=600)
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
        "du -sh /backup/ 2>/dev/null || du -sh /mnt/backup/ 2>/dev/null"
        " || echo 'Backup directory not found.'"
    )
    return {"output": result.stdout.strip()}
