"""System package update handler (apt update/upgrade + rkhunter)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback, safe_answer_callback_query
from linux_server_bot.bot.menus import (
    BTN_SYSTEM_UPDATES,
    inline_action_keyboard,
    inline_confirm_keyboard,
)
from linux_server_bot.shared.actions.system_updates import (
    apply_system_updates,
    check_system_updates,
)
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.telegram import chunk_message, escape_html, send_loading

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_ACTIONS = [
    ("\U0001f50d Check updates", "check"),
    ("✅ Run updates", "run"),
]


def _format_check_result(result: dict) -> str:
    """Format the update check result for Telegram."""
    count = result["count"]
    packages = result["packages"]
    rkhunter = result.get("rkhunter", False)

    if count == 0:
        return "✅ System is up to date. No packages to upgrade."

    lines = [f"\U0001f4e6 <b>{count} package(s) available for upgrade:</b>\n"]
    for pkg in packages:
        lines.append(f"  • {escape_html(pkg)}")

    lines.append(f"\n\U0001f4cb <b>This will run:</b>")
    lines.append("  <code>sudo apt-get upgrade -y</code>")
    if rkhunter:
        lines.append("  <code>sudo rkhunter --propupd</code>")

    return "\n".join(lines)


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register system update handlers."""

    def _send_menu(chat_id: int) -> None:
        markup = inline_action_keyboard("sysupdate", _ACTIONS, row_width=2)
        bot.send_message(chat_id, "System package updates:", reply_markup=markup)

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        chat_id = call.message.chat.id

        if action == "cancel":
            safe_answer_callback_query(bot_inst, call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        if action == "check":
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            loading = send_loading(bot_inst, chat_id, "Checking for updates")
            result = check_system_updates()

            if not result["success"]:
                output = escape_html(result.get("output", "Failed to check for updates."))
                chunks = chunk_message(output)
                if chunks:
                    bot_inst.edit_message_text(chunks[0], chat_id, loading.message_id)
                    for chunk_text in chunks[1:]:
                        bot_inst.send_message(chat_id, chunk_text)
                return

            text = _format_check_result(result)
            bot_inst.edit_message_text(text, chat_id, loading.message_id, parse_mode="HTML")

            if result["count"] > 0:
                markup = inline_confirm_keyboard("sysupdate", "confirm_upgrade")
                bot_inst.send_message(
                    chat_id,
                    f"Apply {result['count']} update(s)?",
                    reply_markup=markup,
                )
            return

        if action == "run":
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            loading = send_loading(bot_inst, chat_id, "Checking for updates")
            result = check_system_updates()

            if not result["success"]:
                output = escape_html(result.get("output", "Failed to check for updates."))
                chunks = chunk_message(output)
                if chunks:
                    bot_inst.edit_message_text(chunks[0], chat_id, loading.message_id)
                    for chunk_text in chunks[1:]:
                        bot_inst.send_message(chat_id, chunk_text)
                return

            text = _format_check_result(result)
            bot_inst.edit_message_text(text, chat_id, loading.message_id, parse_mode="HTML")

            if result["count"] == 0:
                return

            markup = inline_confirm_keyboard("sysupdate", "confirm_upgrade")
            bot_inst.send_message(
                chat_id,
                f"Apply {result['count']} update(s)?",
                reply_markup=markup,
            )
            return

        if action == "confirm_upgrade":
            confirm = parts[1] if len(parts) > 1 else None
            if confirm == "cancel":
                safe_answer_callback_query(bot_inst, call.id, "Cancelled")
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                return
            if confirm == "confirm":
                safe_answer_callback_query(bot_inst, call.id)
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                loading = send_loading(bot_inst, chat_id, "Installing updates")
                result = apply_system_updates()
                output = escape_html(result.get("output", "No output."))
                chunks = chunk_message(output)
                if chunks:
                    bot_inst.edit_message_text(chunks[0], chat_id, loading.message_id)
                    for chunk_text in chunks[1:]:
                        bot_inst.send_message(chat_id, chunk_text)
                icon = "✅" if result["success"] else "⚠️"
                label = "System updates completed." if result["success"] else "Updates finished with errors."
                bot_inst.send_message(chat_id, f"{icon} {label}")
                return

        safe_answer_callback_query(bot_inst, call.id, "Unknown action")

    register_callback("sysupdate", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_SYSTEM_UPDATES)
    @authorized(config)
    def handle_system_updates_menu(message):
        _send_menu(message.chat.id)

    @bot.message_handler(commands=["sysupdate"])
    @authorized(config)
    def handle_system_updates_command(message):
        _send_menu(message.chat.id)
