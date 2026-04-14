"""Custom scripts execution handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback, safe_answer_callback_query
from linux_server_bot.bot.menus import BTN_SCRIPTS, inline_item_keyboard
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.shell import run_shell
from linux_server_bot.shared.telegram import chunk_message, escape_html

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register custom scripts handlers."""

    def _send_scripts_menu(chat_id: int) -> None:
        scripts = config.scripts.custom
        if not scripts:
            bot.send_message(chat_id, "No custom scripts configured in config.yaml.")
            return
        names = [s.name for s in scripts]
        markup = inline_item_keyboard("scripts", "run", names, row_width=1)
        bot.send_message(chat_id, "Which script do you want to run?", reply_markup=markup)

    def _find_script(name: str):
        for s in config.scripts.custom:
            if s.name == name:
                return s
        return None

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        target = ":".join(parts[1:]) if len(parts) > 1 else None
        chat_id = call.message.chat.id

        if action == "cancel":
            safe_answer_callback_query(bot_inst, call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        if action == "run" and target:
            script = _find_script(target)
            if not script:
                safe_answer_callback_query(bot_inst, call.id, "Script not found")
                return

            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            loading = bot_inst.send_message(chat_id, f"\U0001f504 Running {escape_html(script.name)}...")

            logger.info("User running script: %s (%s, timeout=%ds)", script.name, script.path, script.timeout)
            result = run_shell(script.path, timeout=script.timeout)
            output = result.stdout or result.stderr

            if output.strip():
                header = f"<b>{escape_html(script.name)} output:</b>\n"
                chunks = chunk_message(header + escape_html(output))
                if chunks:
                    bot_inst.edit_message_text(chunks[0], chat_id, loading.message_id, parse_mode="HTML")
                    for chunk in chunks[1:]:
                        bot_inst.send_message(chat_id, chunk, parse_mode="HTML")
            else:
                bot_inst.edit_message_text("Script produced no output.", chat_id, loading.message_id)

            icon = "\u2705" if result.success else "\u26a0\ufe0f"
            msg = f"{icon} {escape_html(script.name)} finished (exit code {result.returncode})."
            bot_inst.send_message(chat_id, msg)
            return

        safe_answer_callback_query(bot_inst, call.id, "Unknown action")

    register_callback("scripts", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_SCRIPTS)
    @authorized(config)
    def handle_scripts_menu(message):
        _send_scripts_menu(message.chat.id)

    @bot.message_handler(commands=["scripts"])
    @authorized(config)
    def handle_scripts_command(message):
        _send_scripts_menu(message.chat.id)
