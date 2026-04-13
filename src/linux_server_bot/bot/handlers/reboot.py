"""Server reboot and bot restart handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback, safe_answer_callback_query
from linux_server_bot.bot.menus import BTN_REBOOT, inline_action_keyboard, inline_confirm_keyboard
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.shell import run_command, run_shell

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_ACTIONS = [
    ("\U0001f501 Reboot server", "reboot"),
    ("\U0001f504 Restart bot", "restart_bot"),
]


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register reboot and bot restart handlers."""

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        chat_id = call.message.chat.id

        if action == "cancel":
            safe_answer_callback_query(bot_inst, call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        # "reboot:reboot:confirm" / "reboot:reboot:cancel"
        if action == "reboot" and len(parts) > 1:
            if parts[1] == "confirm":
                safe_answer_callback_query(bot_inst, call.id, "Rebooting...")
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                logger.info("User confirmed server reboot")
                bot_inst.send_message(chat_id, "\U0001f501 Rebooting the server...")
                run_command(["sudo", "reboot", "now"])
                return
            if parts[1] == "cancel":
                safe_answer_callback_query(bot_inst, call.id, "Cancelled")
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                return

        # Show reboot confirmation
        if action == "reboot" and len(parts) == 1:
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            markup = inline_confirm_keyboard("reboot", "reboot")
            bot_inst.send_message(chat_id, "Are you sure you want to reboot the server?", reply_markup=markup)
            return

        # "reboot:restart_bot:confirm" / "reboot:restart_bot:cancel"
        if action == "restart_bot" and len(parts) > 1:
            if parts[1] == "confirm":
                safe_answer_callback_query(bot_inst, call.id, "Restarting bot...")
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                logger.info("User confirmed bot restart")
                bot_inst.send_message(chat_id, "\U0001f504 Restarting bot containers... I'll be back in a moment.")
                # Use docker compose to restart all 3 bot containers
                run_shell("docker compose restart", timeout=60)
                return
            if parts[1] == "cancel":
                safe_answer_callback_query(bot_inst, call.id, "Cancelled")
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                return

        # Show bot restart confirmation
        if action == "restart_bot" and len(parts) == 1:
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            markup = inline_confirm_keyboard("reboot", "restart_bot")
            bot_inst.send_message(
                chat_id,
                "Restart all bot containers (bot, monitoring, API)?",
                reply_markup=markup,
            )
            return

        safe_answer_callback_query(bot_inst, call.id, "Unknown action")

    register_callback("reboot", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_REBOOT)
    @authorized(config)
    def handle_reboot_menu(message):
        markup = inline_action_keyboard("reboot", _ACTIONS, row_width=1)
        bot.send_message(message.chat.id, "Choose an action:", reply_markup=markup)

    @bot.message_handler(commands=["reboot"])
    @authorized(config)
    def handle_reboot_command(message):
        handle_reboot_menu(message)
