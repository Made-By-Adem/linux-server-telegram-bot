"""Server reboot handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.menus import build_confirm_keyboard
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.shell import run_command

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_BTN_REBOOT_NOW = "\U0001f501 Reboot now"
_BTN_CANCEL = "\u274c Cancel reboot"


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register reboot handlers."""

    from linux_server_bot.bot.menus import BTN_REBOOT

    def _show_reboot_confirm(message):
        markup = build_confirm_keyboard(_BTN_REBOOT_NOW, _BTN_CANCEL)
        bot.send_message(message.chat.id, "Are you sure you want to reboot the server?", reply_markup=markup)

    @bot.message_handler(func=lambda m: m.text == BTN_REBOOT)
    @authorized(config)
    def handle_reboot_menu(message):
        _show_reboot_confirm(message)

    @bot.message_handler(commands=["reboot"])
    @authorized(config)
    def handle_reboot_command(message):
        _show_reboot_confirm(message)

    @bot.message_handler(func=lambda m: m.text == _BTN_REBOOT_NOW)
    @authorized(config)
    def handle_reboot_now(message):
        logger.info("User %s requested a reboot", message.from_user.first_name)
        bot.reply_to(message, "Rebooting the server...")
        result = run_command(["sudo", "reboot", "now"])
        if not result.success:
            bot.reply_to(message, f"Reboot failed: {result.stderr}")

    @bot.message_handler(func=lambda m: m.text == _BTN_CANCEL)
    @authorized(config)
    def handle_reboot_cancel(message):
        logger.info("User %s canceled reboot", message.from_user.first_name)
        bot.reply_to(message, "Reboot canceled.")
        show_menu(message)
