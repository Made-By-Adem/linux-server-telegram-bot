"""Log file viewing handlers."""

from __future__ import annotations

import logging
import os
import re
from glob import glob
from typing import TYPE_CHECKING

from linux_server_bot.bot.menus import BTN_BACK_MAIN, BTN_LOGS, build_item_keyboard
from linux_server_bot.shared.auth import authorized

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

# Pattern to detect date-suffixed log files (rotated logs)
_DATE_SUFFIX_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register log viewing handlers."""

    def _show_logs_menu(message):
        markup = build_item_keyboard(config.logfiles, "\U0001f4dc Log:", BTN_BACK_MAIN, row_width=4)
        bot.send_message(message.chat.id, "Which log file do you want to see?", reply_markup=markup)

    @bot.message_handler(func=lambda m: m.text == BTN_LOGS)
    @authorized(config)
    def handle_logs_menu(message):
        _show_logs_menu(message)

    @bot.message_handler(commands=["logs"])
    @authorized(config)
    def handle_logs_command(message):
        _show_logs_menu(message)

    @bot.message_handler(func=lambda m: m.text and m.text.startswith("\U0001f4dc Log: "))
    @authorized(config)
    def handle_log_view(message):
        log_path = message.text.split(": ", 1)[1]
        logger.info("User %s requested log: %s", message.from_user.first_name, log_path)

        # If it's a directory, find .log files inside
        if os.path.isdir(log_path):
            log_files = glob(os.path.join(log_path, "*.log"))
            # Filter out date-rotated files
            log_files = [f for f in log_files if not _DATE_SUFFIX_RE.search(os.path.basename(f))]
        elif os.path.isfile(log_path):
            log_files = [log_path]
        else:
            bot.send_message(message.chat.id, "Log path not found.")
            _show_logs_menu(message)
            return

        if not log_files:
            bot.send_message(message.chat.id, "No log files found.")
            _show_logs_menu(message)
            return

        for log_file in log_files:
            try:
                # Send as document
                with open(log_file, "rb") as f:
                    bot.send_document(message.chat.id, f)

                # Also send last 20 lines
                with open(log_file, "r") as f:
                    lines = f.readlines()
                    tail = "".join(lines[-20:])
                    if tail.strip():
                        bot.send_message(message.chat.id, f"Last 20 lines of {os.path.basename(log_file)}:")
                        bot.send_message(message.chat.id, tail, parse_mode=None)
            except Exception:
                logger.exception("Failed to read log file: %s", log_file)
                bot.send_message(message.chat.id, f"Failed to read {log_file}")

        _show_logs_menu(message)
