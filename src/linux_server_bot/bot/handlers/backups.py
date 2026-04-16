"""Backup trigger and status handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback, safe_answer_callback_query
from linux_server_bot.bot.menus import BTN_BACKUPS, inline_action_keyboard
from linux_server_bot.shared.actions.backups import (
    get_backup_size,
    get_backup_status,
    trigger_backup,
)
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.telegram import chunk_message, escape_html, send_loading

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_STATIC_ACTIONS = [
    ("\U0001f4cb Status", "status"),
    ("\U0001f4c0 Size", "size"),
]


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register backup handlers."""

    def _build_actions() -> list[tuple[str, str]]:
        backup = config.scripts.backup
        actions: list[tuple[str, str]] = []
        if backup.targets:
            for tgt in backup.targets:
                actions.append((f"\u25b6\ufe0f Backup {tgt}", f"trigger:{tgt}"))
        else:
            actions.append(("\u25b6\ufe0f Start backup", "trigger"))
        actions.extend(_STATIC_ACTIONS)
        return actions

    def _send_backups_menu(chat_id: int) -> None:
        markup = inline_action_keyboard("backups", _build_actions(), row_width=3)
        bot.send_message(chat_id, "Backup management:", reply_markup=markup)

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        chat_id = call.message.chat.id

        if action == "cancel":
            safe_answer_callback_query(bot_inst, call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        if action == "trigger":
            backup = config.scripts.backup
            if not backup.path:
                safe_answer_callback_query(bot_inst, call.id, "Script not configured")
                bot_inst.send_message(chat_id, "Backup script not configured in config.yaml (scripts.backup).")
                return
            target = parts[1] if len(parts) > 1 else None
            # Only accept targets that are in the configured allow-list.
            if target and target not in backup.targets:
                safe_answer_callback_query(bot_inst, call.id, "Invalid target")
                return
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            loading_label = f"Backup {target}" if target else "Backup"
            loading = send_loading(bot_inst, chat_id, loading_label)
            result = trigger_backup(backup.path, target)
            output = escape_html(result.get("output", "No output."))
            chunks = chunk_message(output)
            if chunks:
                bot_inst.edit_message_text(chunks[0], chat_id, loading.message_id)
                for chunk_text in chunks[1:]:
                    bot_inst.send_message(chat_id, chunk_text)
            icon = "\u2705" if result["success"] else "\u26a0\ufe0f"
            suffix = f" ({target})" if target else ""
            label = (
                f"Backup{suffix} completed successfully."
                if result["success"]
                else f"Backup{suffix} finished with errors."
            )
            bot_inst.send_message(chat_id, f"{icon} {label}")
            return

        if action == "status":
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            loading = send_loading(bot_inst, chat_id, "Backup status")
            result = get_backup_status()
            output = escape_html(result.get("output", "No backup status available."))
            chunks = chunk_message(output)
            if chunks:
                bot_inst.edit_message_text(chunks[0], chat_id, loading.message_id)
                for chunk_text in chunks[1:]:
                    bot_inst.send_message(chat_id, chunk_text, parse_mode=None)
            return

        if action == "size":
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            loading = send_loading(bot_inst, chat_id, "Backup size")
            result = get_backup_size()
            bot_inst.edit_message_text(
                f"<b>Backup disk usage:</b>\n{escape_html(result.get('output', 'N/A'))}",
                chat_id,
                loading.message_id,
                parse_mode="HTML",
            )
            return

        safe_answer_callback_query(bot_inst, call.id, "Unknown action")

    register_callback("backups", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_BACKUPS)
    @authorized(config)
    def handle_backups_menu(message):
        _send_backups_menu(message.chat.id)

    @bot.message_handler(commands=["backups"])
    @authorized(config)
    def handle_backups_command(message):
        _send_backups_menu(message.chat.id)
