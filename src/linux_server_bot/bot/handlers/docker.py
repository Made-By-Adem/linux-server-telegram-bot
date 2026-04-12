"""Docker container management handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback
from linux_server_bot.bot.menus import (
    BTN_DOCKER,
    inline_action_keyboard,
    inline_item_keyboard,
)
from linux_server_bot.shared.actions.docker import (
    container_action,
    container_action_all,
    get_container_names,
    get_container_statuses_text,
)
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.telegram import escape_html

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


def _send_docker_menu(bot, chat_id: int) -> None:
    markup = inline_action_keyboard("docker", _ACTIONS, row_width=3)
    bot.send_message(chat_id, "What do you want to do?", reply_markup=markup)


def _send_status(bot, chat_id: int) -> None:
    text = get_container_statuses_text()
    bot.send_message(
        chat_id,
        f"<b>Status containers:</b>\n{escape_html(text)}",
        parse_mode="HTML",
    )


def _handle_callback(bot, call, parts: list[str]) -> None:
    action = parts[0] if parts else None
    target = parts[1] if len(parts) > 1 else None
    chat_id = call.message.chat.id

    if action == "cancel":
        bot.answer_callback_query(call.id, "Cancelled")
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
        return

    if action == "status":
        bot.answer_callback_query(call.id, "Fetching status...")
        _send_status(bot, chat_id)
        return

    # Single-container actions requiring target selection
    if action in ("start", "stop", "restart") and not target:
        bot.answer_callback_query(call.id)
        containers = get_container_names()
        if not containers:
            bot.send_message(chat_id, "No containers found.")
            return
        markup = inline_item_keyboard("docker", action, containers, row_width=2)
        bot.send_message(chat_id, f"Which container to {action}?", reply_markup=markup)
        return

    # Execute single-container action
    if action in ("start", "stop", "restart") and target:
        bot.answer_callback_query(call.id, f"{action.capitalize()}ing {target}...")
        result = container_action(action, target)
        icon = "\u2705" if result["success"] else "\u26a0\ufe0f"
        msg = f"{icon} {action.capitalize()} {target}: {'OK' if result['success'] else result['error']}"
        bot.send_message(chat_id, msg)
        _send_status(bot, chat_id)
        return

    # All-container actions
    if action in ("start_all", "stop_all", "restart_all"):
        real_action = action.replace("_all", "")
        bot.answer_callback_query(call.id, f"{real_action.capitalize()}ing all containers...")
        results = container_action_all(real_action)
        failures = [r for r in results if not r["success"]]
        if failures:
            lines = [f"\u26a0\ufe0f {r['name']}: {r['error']}" for r in failures]
            bot.send_message(chat_id, "\n".join(lines))
        _send_status(bot, chat_id)
        return

    bot.answer_callback_query(call.id, "Unknown action")


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register Docker container management handlers."""

    register_callback("docker", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_DOCKER)
    @authorized(config)
    def handle_docker_menu(message):
        _send_status(bot, message.chat.id)
        _send_docker_menu(bot, message.chat.id)

    @bot.message_handler(commands=["docker"])
    @authorized(config)
    def handle_docker_command(message):
        _send_status(bot, message.chat.id)
        _send_docker_menu(bot, message.chat.id)
