"""Container update trigger handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback
from linux_server_bot.bot.menus import BTN_UPDATES, inline_action_keyboard
from linux_server_bot.shared.actions.updates import (
    dry_run_updates,
    rollback_updates,
    trigger_updates,
)
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.telegram import chunk_message, escape_html

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
            bot_inst.answer_callback_query(call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        script = _check_script()
        if not script:
            bot_inst.answer_callback_query(call.id, "Script not configured")
            bot_inst.send_message(chat_id, "Update script not configured in config.yaml (scripts.update_containers).")
            return

        if action == "dry_run":
            bot_inst.answer_callback_query(call.id, "Running dry-run...")
            result = dry_run_updates(script)
            output = result.get("output", "No output.")
            for chunk_text in chunk_message(escape_html(output)):
                bot_inst.send_message(chat_id, chunk_text)
            return

        if action == "run":
            bot_inst.answer_callback_query(call.id, "Starting updates...")
            bot_inst.send_message(chat_id, "Starting container updates (this may take a while)...")
            result = trigger_updates(script)
            output = result.get("output", "No output.")
            for chunk_text in chunk_message(escape_html(output)):
                bot_inst.send_message(chat_id, chunk_text)
            icon = "\u2705" if result["success"] else "\u26a0\ufe0f"
            label = "Container updates completed." if result["success"] else "Updates finished with errors."
            bot_inst.send_message(chat_id, f"{icon} {label}")
            return

        if action == "rollback":
            bot_inst.answer_callback_query(call.id, "Rolling back...")
            result = rollback_updates(script)
            output = result.get("output", "No output.")
            for chunk_text in chunk_message(escape_html(output)):
                bot_inst.send_message(chat_id, chunk_text)
            return

        bot_inst.answer_callback_query(call.id, "Unknown action")

    register_callback("updates", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_UPDATES)
    @authorized(config)
    def handle_updates_menu(message):
        _send_updates_menu(message.chat.id)

    @bot.message_handler(commands=["updates"])
    @authorized(config)
    def handle_updates_command(message):
        _send_updates_menu(message.chat.id)
