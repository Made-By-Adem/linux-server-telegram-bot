"""Systemd service management handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback
from linux_server_bot.bot.menus import (
    BTN_SERVICES,
    inline_action_keyboard,
    inline_item_keyboard,
)
from linux_server_bot.shared.actions.services import (
    get_service_statuses,
    service_action,
    service_action_all,
)
from linux_server_bot.shared.auth import authorized

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_ACTIONS = [
    ("\u25b6 Start", "start"),
    ("\u23f9 Stop", "stop"),
    ("\U0001f504 Restart", "restart"),
    ("\u25b6\u25b6 Start all", "start_all"),
    ("\u23f9\u23f9 Stop all", "stop_all"),
    ("\U0001f504\U0001f504 Restart all", "restart_all"),
    ("\U0001f4ca Status", "status"),
]


def _send_services_menu(bot, chat_id: int) -> None:
    markup = inline_action_keyboard("services", _ACTIONS, row_width=3)
    bot.send_message(chat_id, "What do you want to do?", reply_markup=markup)


def _send_status(bot, chat_id: int, services: list[str]) -> None:
    statuses = get_service_statuses(services)
    lines = ["<b>Status services:</b>"]
    for s in statuses:
        icon = "\u2705" if s.active else "\u274c"
        lines.append(f"{icon} {s.name}: {s.state}")
    bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register all service management handlers."""

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        target = parts[1] if len(parts) > 1 else None
        chat_id = call.message.chat.id

        if action == "cancel":
            bot_inst.answer_callback_query(call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        if action == "status":
            bot_inst.answer_callback_query(call.id, "Fetching status...")
            _send_status(bot_inst, chat_id, config.services)
            return

        if action in ("start", "stop", "restart") and not target:
            bot_inst.answer_callback_query(call.id)
            if not config.services:
                bot_inst.send_message(chat_id, "No services configured.")
                return
            markup = inline_item_keyboard("services", action, config.services, row_width=2)
            bot_inst.send_message(chat_id, f"Which service to {action}?", reply_markup=markup)
            return

        if action in ("start", "stop", "restart") and target:
            bot_inst.answer_callback_query(call.id, f"{action.capitalize()}ing {target}...")
            result = service_action(action, target)
            icon = "\u2705" if result["success"] else "\u26a0\ufe0f"
            msg = f"{icon} {action.capitalize()} {target}: {'OK' if result['success'] else result['error']}"
            bot_inst.send_message(chat_id, msg)
            _send_status(bot_inst, chat_id, config.services)
            return

        if action in ("start_all", "stop_all", "restart_all"):
            real_action = action.replace("_all", "")
            bot_inst.answer_callback_query(call.id, f"{real_action.capitalize()}ing all services...")
            results = service_action_all(real_action, config.services)
            failures = [r for r in results if not r["success"]]
            if failures:
                lines = [f"\u26a0\ufe0f {r['name']}: {r['error']}" for r in failures]
                bot_inst.send_message(chat_id, "\n".join(lines))
            _send_status(bot_inst, chat_id, config.services)
            return

        bot_inst.answer_callback_query(call.id, "Unknown action")

    register_callback("services", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_SERVICES)
    @authorized(config)
    def handle_services_menu(message):
        _send_status(bot, message.chat.id, config.services)
        _send_services_menu(bot, message.chat.id)

    @bot.message_handler(commands=["services"])
    @authorized(config)
    def handle_services_command(message):
        _send_status(bot, message.chat.id, config.services)
        _send_services_menu(bot, message.chat.id)
