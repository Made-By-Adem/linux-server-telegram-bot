"""Security monitoring checks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.shared.shell import run_shell
from linux_server_bot.shared.telegram import escape_html

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)


def check_failed_logins(bot: telebot.TeleBot, config: AppConfig) -> None:
    """Alert on excessive failed login attempts in the last monitoring interval."""
    from linux_server_bot.shared.telegram import send_to_all

    if not config.monitoring.security.get("check_ssh_sessions", True):
        return

    interval = config.monitoring.interval_minutes
    result = run_shell(
        f"journalctl _SYSTEMD_UNIT=sshd.service --since '{interval} minutes ago' --no-pager 2>/dev/null"
        " | grep -ci 'failed\\|invalid'"
        f" || grep -ci 'failed\\|invalid' /var/log/auth.log 2>/dev/null"
    )
    try:
        count = int(result.stdout.strip())
    except (ValueError, IndexError):
        return

    if count > 10:
        logger.warning("Detected %d failed login attempts in last %d minutes", count, interval)
        send_to_all(
            bot,
            config,
            f"\u26a0\ufe0f Brute force alert: {count} failed login attempts in the last {interval} minutes!",
        )


def check_banned_ips(bot: telebot.TeleBot, config: AppConfig) -> None:
    """Check for new fail2ban bans."""
    from linux_server_bot.shared.telegram import send_to_all

    if not config.monitoring.security.get("check_fail2ban", True):
        return

    interval = config.monitoring.interval_minutes
    result = run_shell(
        f"journalctl -u fail2ban --since '{interval} minutes ago' --no-pager 2>/dev/null | grep -i 'ban'"
    )
    bans = result.stdout.strip()
    if bans:
        logger.warning("New fail2ban bans detected")
        send_to_all(
            bot,
            config,
            f"\U0001f6ab New fail2ban bans:\n{escape_html(bans)}",
        )
