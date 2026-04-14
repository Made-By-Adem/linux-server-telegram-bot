"""Security overview handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback, safe_answer_callback_query
from linux_server_bot.bot.menus import BTN_SECURITY, inline_action_keyboard
from linux_server_bot.shared.actions.security import (
    get_available_updates,
    get_fail2ban_status,
    get_failed_logins,
    get_ssh_sessions,
    get_ufw_status,
)
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.telegram import chunk_message, escape_html, send_loading

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_ACTIONS = [
    ("\U0001f6ab Fail2ban", "fail2ban"),
    ("\U0001f525 UFW", "ufw"),
    ("\U0001f464 SSH sessions", "ssh"),
    ("\u26a0\ufe0f Failed logins", "failed"),
    ("\U0001f4e6 Updates", "updates"),
]


def _send_security_menu(bot, chat_id: int) -> None:
    markup = inline_action_keyboard("security", _ACTIONS, row_width=2)
    bot.send_message(chat_id, "Security overview:", reply_markup=markup)


def _handle_callback(bot, call, parts: list[str]) -> None:
    action = parts[0] if parts else None
    chat_id = call.message.chat.id

    if action == "cancel":
        safe_answer_callback_query(bot, call.id, "Cancelled")
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
        return

    if action == "fail2ban":
        safe_answer_callback_query(bot, call.id)
        loading = send_loading(bot, chat_id, "Fail2ban")
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
        result = get_fail2ban_status()
        if result["available"]:
            text = "<b>Fail2ban Status:</b>\n" + escape_html(result["status"])
            bot.edit_message_text(text, chat_id, loading.message_id, parse_mode="HTML")
            if result.get("sshd_jail"):
                bot.send_message(chat_id, "<b>SSH Jail:</b>\n" + escape_html(result["sshd_jail"]), parse_mode="HTML")
        else:
            bot.edit_message_text("Fail2ban not available or not running.", chat_id, loading.message_id)
        return

    if action == "ufw":
        safe_answer_callback_query(bot, call.id)
        loading = send_loading(bot, chat_id, "UFW")
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
        result = get_ufw_status()
        text = "<b>UFW Status:</b>\n" + escape_html(result["status"])
        chunks = chunk_message(text)
        if chunks:
            bot.edit_message_text(chunks[0], chat_id, loading.message_id, parse_mode="HTML")
            for chunk_text in chunks[1:]:
                bot.send_message(chat_id, chunk_text, parse_mode="HTML")
        return

    if action == "ssh":
        safe_answer_callback_query(bot, call.id)
        loading = send_loading(bot, chat_id, "SSH sessions")
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
        result = get_ssh_sessions()
        text = "<b>Current sessions:</b>\n" + escape_html(result["current_sessions"])
        bot.edit_message_text(text, chat_id, loading.message_id, parse_mode="HTML")
        if result.get("recent_logins"):
            text2 = "<b>Last 10 logins:</b>\n" + escape_html(result["recent_logins"])
            bot.send_message(chat_id, text2, parse_mode="HTML")
        return

    if action == "failed":
        safe_answer_callback_query(bot, call.id)
        loading = send_loading(bot, chat_id, "Failed logins")
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
        result = get_failed_logins()
        if result["found"]:
            text = "<b>Recent failed logins:</b>\n" + escape_html(result["output"])
            chunks = chunk_message(text)
            if chunks:
                bot.edit_message_text(chunks[0], chat_id, loading.message_id, parse_mode="HTML")
                for chunk_text in chunks[1:]:
                    bot.send_message(chat_id, chunk_text, parse_mode="HTML")
        else:
            bot.edit_message_text("No recent failed logins found.", chat_id, loading.message_id)
        return

    if action == "updates":
        safe_answer_callback_query(bot, call.id)
        loading = send_loading(bot, chat_id, "Available updates")
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
        result = get_available_updates()
        if result["up_to_date"]:
            bot.edit_message_text("\u2705 System is up to date.", chat_id, loading.message_id)
        else:
            text = "<b>Available updates:</b>\n" + escape_html(result["output"])
            chunks = chunk_message(text)
            if chunks:
                bot.edit_message_text(chunks[0], chat_id, loading.message_id, parse_mode="HTML")
                for chunk_text in chunks[1:]:
                    bot.send_message(chat_id, chunk_text, parse_mode="HTML")
        return

    safe_answer_callback_query(bot, call.id, "Unknown action")


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register security overview handlers."""

    register_callback("security", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_SECURITY)
    @authorized(config)
    def handle_security_menu(message):
        _send_security_menu(bot, message.chat.id)

    @bot.message_handler(commands=["security"])
    @authorized(config)
    def handle_security_command(message):
        _send_security_menu(bot, message.chat.id)
