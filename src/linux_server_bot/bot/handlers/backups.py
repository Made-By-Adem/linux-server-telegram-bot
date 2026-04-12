"""Backup trigger and status handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.menus import BTN_BACK_MAIN, BTN_BACKUPS, build_action_keyboard
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.shell import run_shell
from linux_server_bot.shared.telegram import chunk_message, escape_html

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_BTN_TRIGGER = "\u25b6\ufe0f Start backup"
_BTN_STATUS = "\U0001f4cb Backup status"
_BTN_SIZE = "\U0001f4c0 Backup size"


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register backup handlers."""

    def _show_backups_menu(message):
        actions = [_BTN_TRIGGER, _BTN_STATUS, _BTN_SIZE]
        markup = build_action_keyboard(actions, BTN_BACK_MAIN, row_width=3)
        bot.send_message(message.chat.id, "Backup management:", reply_markup=markup)

    def _check_script():
        script = config.scripts.backup
        if not script:
            return None
        return script

    @bot.message_handler(func=lambda m: m.text == BTN_BACKUPS)
    @authorized(config)
    def handle_backups_menu(message):
        _show_backups_menu(message)

    @bot.message_handler(func=lambda m: m.text == _BTN_TRIGGER)
    @authorized(config)
    def handle_trigger_backup(message):
        script = _check_script()
        if not script:
            bot.send_message(message.chat.id, "Backup script not configured in config.yaml (scripts.backup).")
            _show_backups_menu(message)
            return
        logger.info("User %s triggered backup", message.from_user.first_name)
        bot.reply_to(message, "Starting backup (this may take a while)...")
        result = run_shell(f"sudo {script} 2>&1", timeout=600)
        output = result.stdout or result.stderr or "No output."
        for chunk_text in chunk_message(escape_html(output)):
            bot.send_message(message.chat.id, chunk_text)
        if result.success:
            bot.send_message(message.chat.id, "\u2705 Backup completed successfully.")
        else:
            bot.send_message(message.chat.id, "\u26a0\ufe0f Backup finished with errors.")
        _show_backups_menu(message)

    @bot.message_handler(func=lambda m: m.text == _BTN_STATUS)
    @authorized(config)
    def handle_backup_status(message):
        logger.info("User %s requested backup status", message.from_user.first_name)
        # Check for recent backup logs
        result = run_shell(
            "ls -lt /var/log/backup*.log 2>/dev/null | head -5;"
            " echo '---';"
            " tail -20 /var/log/backup*.log 2>/dev/null || echo 'No backup logs found.'"
        )
        output = result.stdout.strip() or "No backup status available."
        for chunk_text in chunk_message(escape_html(output)):
            bot.send_message(message.chat.id, chunk_text, parse_mode=None)
        _show_backups_menu(message)

    @bot.message_handler(func=lambda m: m.text == _BTN_SIZE)
    @authorized(config)
    def handle_backup_size(message):
        logger.info("User %s requested backup size", message.from_user.first_name)
        result = run_shell(
            "du -sh /backup/ 2>/dev/null || du -sh /mnt/backup/ 2>/dev/null || echo 'Backup directory not found.'"
        )
        bot.send_message(message.chat.id, f"<b>Backup disk usage:</b>\n{escape_html(result.stdout.strip())}")
        _show_backups_menu(message)
