"""Server reboot handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback
from linux_server_bot.bot.menus import BTN_REBOOT, inline_confirm_keyboard
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.shell import run_command

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register reboot handlers."""

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        chat_id = call.message.chat.id

        # "reboot:now:confirm" or "reboot:now:cancel"
        if action == "now" and len(parts) > 1:
            if parts[1] == "confirm":
                bot_inst.answer_callback_query(call.id, "Rebooting...")
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                logger.info("User confirmed reboot")
                bot_inst.send_message(chat_id, "Rebooting the server...")
                result = run_command(["sudo", "reboot", "now"])
                if not result.success:
                    bot_inst.send_message(chat_id, f"Reboot failed: {result.stderr}")
                return
            if parts[1] == "cancel":
                bot_inst.answer_callback_query(call.id, "Cancelled")
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                bot_inst.send_message(chat_id, "Reboot canceled.")
                return

        bot_inst.answer_callback_query(call.id, "Unknown action")

    register_callback("reboot", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_REBOOT)
    @authorized(config)
    def handle_reboot_menu(message):
        markup = inline_confirm_keyboard("reboot", "now")
        bot.send_message(message.chat.id, "Are you sure you want to reboot the server?", reply_markup=markup)
        show_menu(message)

    @bot.message_handler(commands=["reboot"])
    @authorized(config)
    def handle_reboot_command(message):
        handle_reboot_menu(message)
