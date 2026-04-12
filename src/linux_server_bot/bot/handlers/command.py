"""Custom command execution handler using StatesGroup."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telebot.handler_backends import State, StatesGroup

from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.shell import run_shell
from linux_server_bot.shared.telegram import chunk_message, escape_html

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)


class CommandStates(StatesGroup):
    waiting_for_command = State()


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register custom command execution handlers."""

    from linux_server_bot.bot.menus import BTN_COMMAND

    @bot.message_handler(func=lambda m: m.text == BTN_COMMAND)
    @authorized(config)
    def handle_command_menu(message):
        bot.send_message(
            message.chat.id,
            "What command do you want to send to the server? Send /cancel to exit.",
        )
        bot.set_state(message.from_user.id, CommandStates.waiting_for_command, message.chat.id)

    @bot.message_handler(commands=["command"])
    @authorized(config)
    def handle_command_shortcut(message):
        handle_command_menu(message)

    @bot.message_handler(state=CommandStates.waiting_for_command)
    @authorized(config)
    def handle_command_input(message):
        command = message.text
        logger.info("User %s sent command: %s", message.from_user.first_name, command)
        bot.delete_state(message.from_user.id, message.chat.id)

        if command.lower() in ("/cancel", "cancel"):
            bot.reply_to(message, "Command canceled.")
            show_menu(message)
            return

        bot.reply_to(message, f"Sending command: {command}")
        result = run_shell(command, timeout=60)
        output = result.stdout or result.stderr

        if not output.strip():
            bot.send_message(message.chat.id, "The command output is empty.")
        else:
            escaped = escape_html(output)
            for chunk in chunk_message(escaped):
                bot.send_message(message.chat.id, chunk)

        # Prompt for next command
        bot.send_message(
            message.chat.id,
            "Send another command or /cancel to exit.",
        )
        bot.set_state(message.from_user.id, CommandStates.waiting_for_command, message.chat.id)
