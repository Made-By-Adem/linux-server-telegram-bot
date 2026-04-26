"""System package update handler (apt update/upgrade + rkhunter)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback, safe_answer_callback_query
from linux_server_bot.bot.menus import BTN_SYSTEM_UPDATES, inline_action_keyboard
from linux_server_bot.shared.actions.system_updates import (
    dry_run_system_updates,
    trigger_system_updates,
)
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.telegram import chunk_message, escape_html, send_loading

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_ACTIONS = [
    ("\U0001f50d Dry run", "dry_run"),
    ("✅ Run updates", "run"),
]


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register system update handlers."""

    def _send_menu(chat_id: int) -> None:
        markup = inline_action_keyboard("sysupdate", _ACTIONS, row_width=2)
        bot.send_message(chat_id, "System package updates:", reply_markup=markup)

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        chat_id = call.message.chat.id

        if action == "cancel":
            safe_answer_callback_query(bot_inst, call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        if action == "dry_run":
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            loading = send_loading(bot_inst, chat_id, "Checking for updates")
            result = dry_run_system_updates()
            output = escape_html(result.get("output", "No output."))
            chunks = chunk_message(output)
            if chunks:
                bot_inst.edit_message_text(chunks[0], chat_id, loading.message_id)
                for chunk_text in chunks[1:]:
                    bot_inst.send_message(chat_id, chunk_text)
            return

        if action == "run":
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            loading = send_loading(bot_inst, chat_id, "System updates")
            result = trigger_system_updates()
            output = escape_html(result.get("output", "No output."))
            chunks = chunk_message(output)
            if chunks:
                bot_inst.edit_message_text(chunks[0], chat_id, loading.message_id)
                for chunk_text in chunks[1:]:
                    bot_inst.send_message(chat_id, chunk_text)
            icon = "✅" if result["success"] else "⚠️"
            label = "System updates completed." if result["success"] else "Updates finished with errors."
            bot_inst.send_message(chat_id, f"{icon} {label}")
            return

        safe_answer_callback_query(bot_inst, call.id, "Unknown action")

    register_callback("sysupdate", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_SYSTEM_UPDATES)
    @authorized(config)
    def handle_system_updates_menu(message):
        _send_menu(message.chat.id)

    @bot.message_handler(commands=["sysupdate"])
    @authorized(config)
    def handle_system_updates_command(message):
        _send_menu(message.chat.id)
