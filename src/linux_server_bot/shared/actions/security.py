"""Security actions -- shared between bot and API."""

from __future__ import annotations

import logging

from linux_server_bot.shared.shell import run_command, run_shell

logger = logging.getLogger(__name__)


def get_fail2ban_status() -> dict:
    """Get fail2ban status including sshd jail."""
    status = run_command(["sudo", "fail2ban-client", "status"])
    jail = run_command(["sudo", "fail2ban-client", "status", "sshd"])
    return {
        "available": status.success,
        "status": status.stdout if status.success else "Not available",
        "sshd_jail": jail.stdout if jail.success else None,
    }


def get_ufw_status() -> dict:
    """Get UFW firewall status."""
    result = run_command(["sudo", "ufw", "status", "verbose"])
    return {
        "available": result.success,
        "status": result.stdout if result.success else "Not available",
    }


def get_ssh_sessions() -> dict:
    """Get current SSH sessions and recent logins."""
    who = run_command(["who"])
    last = run_command(["last", "-n", "10"])
    return {
        "current_sessions": who.stdout.strip() or "No active sessions",
        "recent_logins": last.stdout.strip() if last.success else "",
    }


def get_failed_logins() -> dict:
    """Get recent failed login attempts."""
    result = run_shell(
        "journalctl _SYSTEMD_UNIT=sshd.service --no-pager -n 50 2>/dev/null"
        " | grep -i 'failed\\|invalid' | tail -20"
        " || grep -i 'failed\\|invalid' /var/log/auth.log 2>/dev/null | tail -20"
    )
    return {"output": result.stdout.strip(), "found": bool(result.stdout.strip())}


def get_available_updates() -> dict:
    """Check for available system updates."""
    result = run_shell(
        "if command -v apt &>/dev/null; then"
        "  sudo apt update -qq 2>/dev/null && apt list --upgradable 2>/dev/null;"
        "elif command -v yum &>/dev/null; then"
        "  sudo yum check-update 2>/dev/null;"
        "else echo 'Unsupported package manager'; fi"
    )
    return {"output": result.stdout.strip(), "up_to_date": not bool(result.stdout.strip())}


def get_full_security_status() -> dict:
    """Get complete security overview."""
    return {
        "fail2ban": get_fail2ban_status(),
        "ufw": get_ufw_status(),
        "ssh": get_ssh_sessions(),
        "failed_logins": get_failed_logins(),
        "updates": get_available_updates(),
    }
