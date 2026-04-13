"""Backup trigger and status handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback
from linux_server_bot.bot.menus import BTN_BACKUPS, inline_action_keyboard
from linux_server_bot.shared.actions.backups import (
    get_backup_size,
    get_backup_status,
    trigger_backup,
)
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.telegram import chunk_message, escape_html

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_ACTIONS = [
    ("\u25b6\ufe0f Start backup", "trigger"),
    ("\U0001f4cb Status", "status"),
    ("\U0001f4c0 Size", "size"),
]


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register backup handlers."""

    def _send_backups_menu(chat_id: int) -> None:
        markup = inline_action_keyboard("backups", _ACTIONS, row_width=3)
        bot.send_message(chat_id, "Backup management:", reply_markup=markup)

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        chat_id = call.message.chat.id

        if action == "cancel":
            bot_inst.answer_callback_query(call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        if action == "trigger":
            script = config.scripts.backup
            if not script:
                bot_inst.answer_callback_query(call.id, "Script not configured")
                bot_inst.send_message(chat_id, "Backup script not configured in config.yaml (scripts.backup).")
                return
            bot_inst.answer_callback_query(call.id, "Starting backup...")
            bot_inst.send_message(chat_id, "Starting backup (this may take a while)...")
            result = trigger_backup(script)
            output = result.get("output", "No output.")
            for chunk_text in chunk_message(escape_html(output)):
                bot_inst.send_message(chat_id, chunk_text)
            icon = "\u2705" if result["success"] else "\u26a0\ufe0f"
            label = "Backup completed successfully." if result["success"] else "Backup finished with errors."
            bot_inst.send_message(chat_id, f"{icon} {label}")
            return

        if action == "status":
            bot_inst.answer_callback_query(call.id, "Checking status...")
            result = get_backup_status()
            output = result.get("output", "No backup status available.")
            for chunk_text in chunk_message(escape_html(output)):
                bot_inst.send_message(chat_id, chunk_text, parse_mode=None)
            return

        if action == "size":
            bot_inst.answer_callback_query(call.id, "Checking size...")
            result = get_backup_size()
            bot_inst.send_message(
                chat_id,
                f"<b>Backup disk usage:</b>\n{escape_html(result.get('output', 'N/A'))}",
                parse_mode="HTML",
            )
            return

        bot_inst.answer_callback_query(call.id, "Unknown action")

    register_callback("backups", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_BACKUPS)
    @authorized(config)
    def handle_backups_menu(message):
        _send_backups_menu(message.chat.id)

    @bot.message_handler(commands=["backups"])
    @authorized(config)
    def handle_backups_command(message):
        _send_backups_menu(message.chat.id)
