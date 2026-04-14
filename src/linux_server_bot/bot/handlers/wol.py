"""Wake-on-LAN handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback, safe_answer_callback_query
from linux_server_bot.bot.menus import BTN_WOL, inline_confirm_keyboard
from linux_server_bot.shared.actions.wol import wake_device
from linux_server_bot.shared.auth import authorized

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register WoL handlers."""

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        chat_id = call.message.chat.id

        # "wol:wake:confirm" or "wol:wake:cancel"
        if action == "wake" and len(parts) > 1:
            if parts[1] == "confirm":
                safe_answer_callback_query(bot_inst, call.id, "Sending WoL packet...")
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                logger.info("User triggered WoL for %s", config.wol.hostname)
                result = wake_device(config.wol.address, config.wol.interface)
                if result["success"]:
                    bot_inst.send_message(chat_id, f"\u2705 Wake-on-LAN packet sent to {config.wol.hostname}.")
                else:
                    bot_inst.send_message(chat_id, f"\u26a0\ufe0f WoL failed: {result['error']}")
                return
            if parts[1] == "cancel":
                safe_answer_callback_query(bot_inst, call.id, "Cancelled")
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                bot_inst.send_message(chat_id, "Wake up canceled.")
                return

        safe_answer_callback_query(bot_inst, call.id, "Unknown action")

    register_callback("wol", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_WOL)
    @authorized(config)
    def handle_wol_menu(message):
        hostname = config.wol.hostname or "device"
        markup = inline_confirm_keyboard("wol", "wake")
        bot.send_message(
            message.chat.id,
            f"Do you want to wake up <b>{hostname}</b>?",
            reply_markup=markup,
            parse_mode="HTML",
        )

    @bot.message_handler(commands=["wakewol"])
    @authorized(config)
    def handle_wol_command(message):
        handle_wol_menu(message)
