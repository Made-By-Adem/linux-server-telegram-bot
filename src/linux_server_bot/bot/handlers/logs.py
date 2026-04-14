"""Log file viewing handlers."""

from __future__ import annotations

import io
import logging
import os
import re
from glob import glob
from typing import TYPE_CHECKING

from telebot import types

from linux_server_bot.bot.callbacks import register_callback, safe_answer_callback_query
from linux_server_bot.bot.menus import BTN_LOGS
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.telegram import chunk_message, escape_html

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

# Pattern to detect date-suffixed log files (rotated logs)
_DATE_SUFFIX_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

# Per-chat cache mapping index -> log path (avoids long paths in callback_data)
_log_path_cache: dict[int, list[str]] = {}


def _is_glob(path: str) -> bool:
    """Check if a path contains glob wildcard characters."""
    return any(c in path for c in ("*", "?", "["))


def _build_log_index(bot, chat_id: int, paths: list[str]) -> types.InlineKeyboardMarkup:
    """Build an index-based inline keyboard for a list of log file paths.

    Uses numeric indexes as callback_data to stay within Telegram's 64-byte limit.
    The paths are stored in ``_log_path_cache`` keyed by ``chat_id``.
    """
    _log_path_cache[chat_id] = paths
    markup = types.InlineKeyboardMarkup(row_width=1)
    for idx, path in enumerate(paths):
        label = os.path.basename(path)
        markup.add(types.InlineKeyboardButton(label, callback_data=f"logs:view:{idx}"))
    markup.add(types.InlineKeyboardButton("\u274c Cancel", callback_data="logs:cancel"))
    return markup


def _send_log_file(bot, chat_id: int, log_file: str) -> None:
    """Send a single log file as document + tail preview."""
    try:
        if os.path.getsize(log_file) == 0:
            bot.send_message(chat_id, f"{os.path.basename(log_file)} is empty.")
            return
    except OSError:
        logger.exception("Failed to stat log file: %s", log_file)
        bot.send_message(chat_id, f"Failed to read {log_file}")
        return

    # Send as .txt so it's easy to open on mobile
    txt_name = os.path.splitext(os.path.basename(log_file))[0] + ".txt"
    try:
        with open(log_file, "rb") as f:
            buf = io.BytesIO(f.read())
            buf.name = txt_name
            bot.send_document(chat_id, buf)
    except Exception:
        logger.exception("Failed to send log file: %s", log_file)
        bot.send_message(chat_id, f"Failed to send {log_file}")
        return

    try:
        with open(log_file, "r", errors="replace") as f:
            # Read only the last 20 lines efficiently
            tail_lines = _tail_lines(f, 20)
            tail = "".join(tail_lines)
            if tail.strip():
                header = f"<b>Last 20 lines of {escape_html(os.path.basename(log_file))}:</b>\n"
                for chunk in chunk_message(header + escape_html(tail)):
                    bot.send_message(chat_id, chunk, parse_mode="HTML")
    except Exception:
        logger.exception("Failed to read log tail: %s", log_file)
        bot.send_message(chat_id, f"Failed to read {log_file}")


def _tail_lines(f, n: int) -> list[str]:
    """Read the last *n* lines from a file object efficiently (seek from EOF)."""
    try:
        f.seek(0, 2)  # seek to end
        size = f.tell()
    except OSError:
        # Not seekable, fall back to reading all
        return f.readlines()[-n:]

    if size == 0:
        return []

    # Read backwards in chunks to find enough newlines
    block_size = 4096
    data = ""
    pos = size
    while pos > 0 and data.count("\n") <= n:
        read_size = min(block_size, pos)
        pos -= read_size
        f.seek(pos)
        data = f.read(read_size) + data

    return data.splitlines(keepends=True)[-n:]


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
            recent = matches[:5]
            markup = _build_log_index(bot, chat_id, recent)
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
        _send_log_file(bot, chat_id, log_file)


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

        # Use index-based callbacks to avoid 64-byte callback_data limit
        _log_path_cache[chat_id] = available
        markup = types.InlineKeyboardMarkup(row_width=1)
        for idx, path in enumerate(available):
            label = os.path.basename(path.rstrip("/")) or path
            markup.add(types.InlineKeyboardButton(label, callback_data=f"logs:view:{idx}"))
        markup.add(types.InlineKeyboardButton("\u274c Cancel", callback_data="logs:cancel"))

        msg = "Which log file do you want to see?"
        if missing:
            msg += "\n\nNot found on this server:\n" + "\n".join(f"  - {p}" for p in missing)
        bot.send_message(chat_id, msg, reply_markup=markup)

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        target = parts[1] if len(parts) > 1 else None
        chat_id = call.message.chat.id

        if action == "cancel":
            safe_answer_callback_query(bot_inst, call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        if action == "view" and target is not None:
            try:
                idx = int(target)
            except ValueError:
                safe_answer_callback_query(bot_inst, call.id, "Invalid selection")
                return

            cached = _log_path_cache.get(chat_id, [])
            if idx < 0 or idx >= len(cached):
                safe_answer_callback_query(bot_inst, call.id, "Selection expired, try again")
                return

            log_path = cached[idx]
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            bot_inst.send_message(chat_id, f"\U0001f504 Loading {escape_html(os.path.basename(log_path))}...")
            logger.info("User requested log: %s", log_path)
            _view_log(bot_inst, chat_id, log_path)
            return

        safe_answer_callback_query(bot_inst, call.id, "Unknown action")

    register_callback("logs", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_LOGS)
    @authorized(config)
    def handle_logs_menu(message):
        bot.send_message(message.chat.id, "\U0001f504 Loading Logs...")
        _send_logs_menu(message.chat.id)

    @bot.message_handler(commands=["logs"])
    @authorized(config)
    def handle_logs_command(message):
        bot.send_message(message.chat.id, "\U0001f504 Loading Logs...")
        _send_logs_menu(message.chat.id)
