"""Log file viewing handlers."""

from __future__ import annotations

import logging
import os
import re
from glob import glob
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback
from linux_server_bot.bot.menus import BTN_LOGS, inline_item_keyboard
from linux_server_bot.shared.auth import authorized

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

# Pattern to detect date-suffixed log files (rotated logs)
_DATE_SUFFIX_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _is_glob(path: str) -> bool:
    """Check if a path contains glob wildcard characters."""
    return any(c in path for c in ("*", "?", "["))


def _view_log(bot, chat_id: int, log_path: str) -> None:
    """Read and send a log file, directory of log files, or glob pattern (latest match)."""
    if _is_glob(log_path):
        matches = sorted(glob(log_path), key=os.path.getmtime, reverse=True)
        if not matches:
            bot.send_message(chat_id, "No log files found.")
            return
        if len(matches) == 1:
            log_files = matches
        else:
            recent = [os.path.basename(f) for f in matches[:5]]
            parent = os.path.dirname(matches[0])
            full_paths = [os.path.join(parent, f) for f in recent]
            markup = inline_item_keyboard("logs", "view", full_paths, row_width=1)
            bot.send_message(chat_id, "Pick a log file (most recent first):", reply_markup=markup)
            return
    elif os.path.isdir(log_path):
        log_files = glob(os.path.join(log_path, "*.log"))
        log_files = [f for f in log_files if not _DATE_SUFFIX_RE.search(os.path.basename(f))]
    elif os.path.isfile(log_path):
        log_files = [log_path]
    else:
        bot.send_message(chat_id, "Log path not found.")
        return

    if not log_files:
        bot.send_message(chat_id, "No log files found.")
        return

    for log_file in log_files:
        try:
            if os.path.getsize(log_file) == 0:
                bot.send_message(chat_id, f"{os.path.basename(log_file)} is empty.")
                continue
        except OSError:
            logger.exception("Failed to stat log file: %s", log_file)
            bot.send_message(chat_id, f"Failed to read {log_file}")
            continue

        try:
            with open(log_file, "rb") as f:
                bot.send_document(chat_id, f)
        except Exception:
            logger.exception("Failed to send log file: %s", log_file)
            bot.send_message(chat_id, f"Failed to send {log_file}")
            continue

        try:
            with open(log_file, "r") as f:
                lines = f.readlines()
                tail = "".join(lines[-20:])
                if tail.strip():
                    bot.send_message(chat_id, f"Last 20 lines of {os.path.basename(log_file)}:")
                    bot.send_message(chat_id, tail, parse_mode=None)
        except Exception:
            logger.exception("Failed to read log tail: %s", log_file)
            bot.send_message(chat_id, f"Failed to read {log_file}")


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register log viewing handlers."""

    def _send_logs_menu(chat_id: int) -> None:
        if not config.logfiles:
            bot.send_message(chat_id, "No log files configured.")
            return

        # Show which paths exist and which don't
        available = []
        missing = []
        for path in config.logfiles:
            if _is_glob(path) or os.path.exists(path):
                available.append(path)
            else:
                missing.append(path)

        if not available and missing:
            msg = "No log files found on this server.\n\nMissing paths:\n"
            msg += "\n".join(f"  - {p}" for p in missing)
            bot.send_message(chat_id, msg)
            return

        markup = inline_item_keyboard("logs", "view", available, row_width=1)
        msg = "Which log file do you want to see?"
        if missing:
            msg += "\n\nNot found on this server:\n" + "\n".join(f"  - {p}" for p in missing)
        bot.send_message(chat_id, msg, reply_markup=markup)

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        target = ":".join(parts[1:]) if len(parts) > 1 else None
        chat_id = call.message.chat.id

        if action == "cancel":
            bot_inst.answer_callback_query(call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        if action == "view" and target:
            bot_inst.answer_callback_query(call.id, f"Loading {target}...")
            logger.info("User requested log: %s", target)
            _view_log(bot_inst, chat_id, target)
            return

        bot_inst.answer_callback_query(call.id, "Unknown action")

    register_callback("logs", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_LOGS)
    @authorized(config)
    def handle_logs_menu(message):
        _send_logs_menu(message.chat.id)

    @bot.message_handler(commands=["logs"])
    @authorized(config)
    def handle_logs_command(message):
        _send_logs_menu(message.chat.id)
