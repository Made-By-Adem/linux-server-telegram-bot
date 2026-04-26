"""System package update actions -- shared between bot and API."""

from __future__ import annotations

import logging

from linux_server_bot.shared.shell import run_command, run_shell

logger = logging.getLogger(__name__)

_APT_TIMEOUT = 600


def _rkhunter_installed() -> bool:
    result = run_shell("command -v rkhunter", timeout=5)
    return result.success


def _parse_upgradable(output: str) -> list[str]:
    """Extract package lines from `apt list --upgradable` output."""
    lines = []
    for line in output.strip().splitlines():
        if line.startswith("Listing") or not line.strip():
            continue
        lines.append(line)
    return lines


def check_system_updates() -> dict:
    """Run apt update and list available upgrades without installing."""
    logger.info("Checking for system updates")
    update = run_command(["sudo", "apt-get", "update"], timeout=_APT_TIMEOUT)
    if not update.success:
        return {
            "success": False,
            "packages": [],
            "count": 0,
            "output": update.stdout + "\n" + update.stderr,
        }

    upgradable = run_command(["apt", "list", "--upgradable"], timeout=30)
    packages = _parse_upgradable(upgradable.stdout)

    return {
        "success": True,
        "packages": packages,
        "count": len(packages),
        "rkhunter": _rkhunter_installed(),
        "output": update.stdout + "\n" + upgradable.stdout,
    }


def apply_system_updates() -> dict:
    """Run apt upgrade -y, then rkhunter --propupd if installed."""
    logger.info("Applying system updates")
    lines: list[str] = []

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
