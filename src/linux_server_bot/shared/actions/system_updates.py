"""System package update actions -- shared between bot and API."""

from __future__ import annotations

import logging

from linux_server_bot.shared.shell import run_command, run_shell

logger = logging.getLogger(__name__)

_APT_TIMEOUT = 600


def _rkhunter_installed() -> bool:
    result = run_shell("command -v rkhunter", timeout=5)
    return result.success


def dry_run_system_updates() -> dict:
    """Show available system package updates without installing."""
    logger.info("System update dry-run")
    result = run_command(["sudo", "apt-get", "update"], timeout=_APT_TIMEOUT)
    if not result.success:
        return {"success": False, "output": result.stdout + "\n" + result.stderr}

    upgradable = run_command(["apt", "list", "--upgradable"], timeout=30)
    output = result.stdout + "\n" + upgradable.stdout
    return {"success": True, "output": output}


def trigger_system_updates() -> dict:
    """Run apt update && apt upgrade -y, then rkhunter --propupd if installed."""
    logger.info("Triggering system updates")
    lines: list[str] = []

    update = run_command(["sudo", "apt-get", "update"], timeout=_APT_TIMEOUT)
    lines.append(update.stdout)
    if not update.success:
        lines.append(update.stderr)
        return {"success": False, "output": "\n".join(lines)}

    upgrade = run_command(
        ["sudo", "apt-get", "upgrade", "-y"],
        timeout=_APT_TIMEOUT,
    )
    lines.append(upgrade.stdout)
    if upgrade.stderr:
        lines.append(upgrade.stderr)

    if upgrade.success and _rkhunter_installed():
        logger.info("rkhunter detected, running --propupd")
        rk = run_command(["sudo", "rkhunter", "--propupd"], timeout=120)
        lines.append("\n--- rkhunter --propupd ---")
        lines.append(rk.stdout)
        if rk.stderr:
            lines.append(rk.stderr)

    return {"success": upgrade.success, "output": "\n".join(lines)}
