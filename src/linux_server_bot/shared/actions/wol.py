"""Wake-on-LAN actions -- shared between bot and API."""

from __future__ import annotations

import logging

from linux_server_bot.shared.shell import run_command

logger = logging.getLogger(__name__)


def wake_device(address: str, interface: str = "eth0") -> dict:
    """Send a WoL magic packet."""
    logger.info("Sending WoL to %s via %s", address, interface)
    result = run_command(["sudo", "etherwake", "-i", interface, address])
    return {"success": result.success, "error": result.stderr if not result.success else ""}
