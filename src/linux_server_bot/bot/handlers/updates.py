"""Container update trigger handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback, safe_answer_callback_query
from linux_server_bot.bot.menus import BTN_UPDATES, inline_action_keyboard
from linux_server_bot.shared.actions.updates import (
    dry_run_updates,
    rollback_updates,
    trigger_updates,
)
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.telegram import chunk_message, escape_html, send_loading

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_ACTIONS = [
    ("\U0001f50d Dry run", "dry_run"),
    ("\u2705 Run updates", "run"),
    ("\u21a9\ufe0f Rollback", "rollback"),
]


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register container update trigger handlers."""

    def _send_updates_menu(chat_id: int) -> None:
        markup = inline_action_keyboard("updates", _ACTIONS, row_width=3)
        bot.send_message(chat_id, "Container updates:", reply_markup=markup)

    def _check_script() -> str | None:
        script = config.scripts.update_containers
        return script if script else None

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        chat_id = call.message.chat.id

        if action == "cancel":
            safe_answer_callback_query(bot_inst, call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        script = _check_script()
        if not script:
            safe_answer_callback_query(bot_inst, call.id, "Script not configured")
            bot_inst.send_message(chat_id, "Update script not configured in config.yaml (scripts.update_containers).")
            return

        if action == "dry_run":
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            loading = send_loading(bot_inst, chat_id, "Dry-run")
            result = dry_run_updates(script)
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
            loading = send_loading(bot_inst, chat_id, "Container updates")
            result = trigger_updates(script)
            output = escape_html(result.get("output", "No output."))
            chunks = chunk_message(output)
            if chunks:
                bot_inst.edit_message_text(chunks[0], chat_id, loading.message_id)
                for chunk_text in chunks[1:]:
                    bot_inst.send_message(chat_id, chunk_text)
            icon = "\u2705" if result["success"] else "\u26a0\ufe0f"
            label = "Container updates completed." if result["success"] else "Updates finished with errors."
            bot_inst.send_message(chat_id, f"{icon} {label}")
            return

        if action == "rollback":
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            loading = send_loading(bot_inst, chat_id, "Rollback")
            result = rollback_updates(script)
            output = escape_html(result.get("output", "No output."))
            chunks = chunk_message(output)
            if chunks:
                bot_inst.edit_message_text(chunks[0], chat_id, loading.message_id)
                for chunk_text in chunks[1:]:
                    bot_inst.send_message(chat_id, chunk_text)
            return

        safe_answer_callback_query(bot_inst, call.id, "Unknown action")

    register_callback("updates", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_UPDATES)
    @authorized(config)
    def handle_updates_menu(message):
        _send_updates_menu(message.chat.id)

    @bot.message_handler(commands=["updates"])
    @authorized(config)
    def handle_updates_command(message):
        _send_updates_menu(message.chat.id)
