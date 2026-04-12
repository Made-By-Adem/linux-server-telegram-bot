"""Security overview handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.menus import BTN_BACK_MAIN, BTN_SECURITY, build_action_keyboard
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.shell import run_command, run_shell
from linux_server_bot.shared.telegram import chunk_message, escape_html

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_BTN_FAIL2BAN = "\U0001f6ab Fail2ban status"
_BTN_UFW = "\U0001f525 UFW status"
_BTN_SSH = "\U0001f464 SSH sessions"
_BTN_FAILED = "\u26a0\ufe0f Failed logins"
_BTN_UPDATES = "\U0001f4e6 Available updates"


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register security overview handlers."""

    def _show_security_menu(message):
        actions = [_BTN_FAIL2BAN, _BTN_UFW, _BTN_SSH, _BTN_FAILED, _BTN_UPDATES]
        markup = build_action_keyboard(actions, BTN_BACK_MAIN, row_width=2)
        bot.send_message(message.chat.id, "Security overview:", reply_markup=markup)

    @bot.message_handler(func=lambda m: m.text == BTN_SECURITY)
    @authorized(config)
    def handle_security_menu(message):
        _show_security_menu(message)

    @bot.message_handler(func=lambda m: m.text == _BTN_FAIL2BAN)
    @authorized(config)
    def handle_fail2ban(message):
        logger.info("User %s requested fail2ban status", message.from_user.first_name)
        result = run_command(["sudo", "fail2ban-client", "status"])
        if result.success:
            text = "<b>Fail2ban Status:</b>\n" + escape_html(result.stdout)
        else:
            text = "Fail2ban not available or not running."
        bot.send_message(message.chat.id, text)

        # Also get sshd jail details if available
        jail_result = run_command(["sudo", "fail2ban-client", "status", "sshd"])
        if jail_result.success:
            bot.send_message(message.chat.id, "<b>SSH Jail:</b>\n" + escape_html(jail_result.stdout))
        _show_security_menu(message)

    @bot.message_handler(func=lambda m: m.text == _BTN_UFW)
    @authorized(config)
    def handle_ufw(message):
        logger.info("User %s requested UFW status", message.from_user.first_name)
        result = run_command(["sudo", "ufw", "status", "verbose"])
        text = "<b>UFW Status:</b>\n" + escape_html(result.stdout if result.success else "UFW not available.")
        for chunk in chunk_message(text):
            bot.send_message(message.chat.id, chunk)
        _show_security_menu(message)

    @bot.message_handler(func=lambda m: m.text == _BTN_SSH)
    @authorized(config)
    def handle_ssh_sessions(message):
        logger.info("User %s requested SSH sessions", message.from_user.first_name)
        who_result = run_command(["who"])
        text = "<b>Current sessions:</b>\n" + escape_html(who_result.stdout or "No active sessions.")
        bot.send_message(message.chat.id, text)

        last_result = run_command(["last", "-n", "10"])
        if last_result.success and last_result.stdout.strip():
            bot.send_message(message.chat.id, "<b>Last 10 logins:</b>\n" + escape_html(last_result.stdout))
        _show_security_menu(message)

    @bot.message_handler(func=lambda m: m.text == _BTN_FAILED)
    @authorized(config)
    def handle_failed_logins(message):
        logger.info("User %s requested failed logins", message.from_user.first_name)
        result = run_shell(
            "journalctl _SYSTEMD_UNIT=sshd.service --no-pager -n 50 2>/dev/null"
            " | grep -i 'failed\\|invalid' | tail -20"
            " || grep -i 'failed\\|invalid' /var/log/auth.log 2>/dev/null | tail -20"
        )
        output = result.stdout.strip()
        if output:
            text = "<b>Recent failed logins:</b>\n" + escape_html(output)
            for chunk in chunk_message(text):
                bot.send_message(message.chat.id, chunk)
        else:
            bot.send_message(message.chat.id, "No recent failed logins found.")
        _show_security_menu(message)

    @bot.message_handler(func=lambda m: m.text == _BTN_UPDATES)
    @authorized(config)
    def handle_updates_check(message):
        logger.info("User %s checking available updates", message.from_user.first_name)
        result = run_shell(
            "if command -v apt &>/dev/null; then"
            "  sudo apt update -qq 2>/dev/null && apt list --upgradable 2>/dev/null;"
            "elif command -v yum &>/dev/null; then"
            "  sudo yum check-update 2>/dev/null;"
            "else echo 'Unsupported package manager'; fi"
        )
        output = result.stdout.strip()
        if output:
            text = "<b>Available updates:</b>\n" + escape_html(output)
            for chunk in chunk_message(text):
                bot.send_message(message.chat.id, chunk)
        else:
            bot.send_message(message.chat.id, "System is up to date.")
        _show_security_menu(message)
