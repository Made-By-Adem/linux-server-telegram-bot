"""Wake-on-LAN handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.menus import BTN_WOL, build_confirm_keyboard
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.shell import run_command

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_BTN_WAKE = "\U0001f4bb Wake up"
_BTN_CANCEL = "\u274c Cancel wake up"


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register WoL handlers."""

    @bot.message_handler(func=lambda m: m.text == BTN_WOL)
    @authorized(config)
    def handle_wol_menu(message):
        markup = build_confirm_keyboard(_BTN_WAKE, _BTN_CANCEL)
        hostname = config.wol.hostname or "device"
        bot.send_message(
            message.chat.id,
            f"Do you want to wake up <b>{hostname}</b>?",
            reply_markup=markup,
        )

    @bot.message_handler(func=lambda m: m.text == _BTN_WAKE)
    @authorized(config)
    def handle_wol_now(message):
        logger.info("User %s triggered WoL for %s", message.from_user.first_name, config.wol.hostname)
        bot.reply_to(message, f"Waking up {config.wol.hostname}...")
        result = run_command([
            "sudo", "etherwake", "-i", config.wol.interface, config.wol.address,
        ])
        if result.success:
            bot.send_message(message.chat.id, f"\u2705 Wake-on-LAN packet sent to {config.wol.hostname}.")
        else:
            bot.send_message(message.chat.id, f"\u26a0\ufe0f WoL failed: {result.stderr}")
        show_menu(message)

    @bot.message_handler(func=lambda m: m.text == _BTN_CANCEL)
    @authorized(config)
    def handle_wol_cancel(message):
        bot.reply_to(message, "Wake up canceled.")
        show_menu(message)

    @bot.message_handler(commands=["wakewol"])
    @authorized(config)
    def handle_wol_command(message):
        handle_wol_menu(message)
