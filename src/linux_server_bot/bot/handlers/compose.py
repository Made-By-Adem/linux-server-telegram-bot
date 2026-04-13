"""Docker Compose stack management handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback
from linux_server_bot.bot.menus import (
    BTN_COMPOSE,
    inline_action_keyboard,
    inline_item_keyboard,
)
from linux_server_bot.shared.actions.compose import (
    get_stack_status,
    stack_down,
    stack_logs,
    stack_pull_recreate,
    stack_restart,
    stack_up,
)
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.telegram import chunk_message, escape_html

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig, ComposeStack

logger = logging.getLogger(__name__)

_ACTIONS = [
    ("\U0001f4ca Status", "status"),
    ("\u25b6 Up", "up"),
    ("\u23f9 Down", "down"),
    ("\U0001f504 Restart", "restart"),
    ("\u2b07\ufe0f Pull & recreate", "pull"),
    ("\U0001f4dc Logs", "logs"),
]


def _find_stack(stacks: list[ComposeStack], name: str) -> ComposeStack | None:
    for s in stacks:
        if s.name == name:
            return s
    return None


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register Docker Compose stack management handlers."""

    def _send_compose_menu(chat_id: int) -> None:
        markup = inline_action_keyboard("compose", _ACTIONS, row_width=3)
        bot.send_message(chat_id, "Docker Compose stack management:", reply_markup=markup)

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        target = parts[1] if len(parts) > 1 else None
        chat_id = call.message.chat.id
        stack_names = [s.name for s in config.compose_stacks]

        if action == "cancel":
            bot_inst.answer_callback_query(call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        if action == "status":
            bot_inst.answer_callback_query(call.id, "Fetching status...")
            for stack in config.compose_stacks:
                result = get_stack_status(stack)
                header = f"<b>{stack.name}</b> ({stack.path}):\n"
                output = escape_html(result["output"])
                bot_inst.send_message(chat_id, header + output, parse_mode="HTML")
            return

        # Actions requiring stack selection
        if action in ("up", "down", "restart", "pull", "logs") and not target:
            bot_inst.answer_callback_query(call.id)
            if not stack_names:
                bot_inst.send_message(chat_id, "No compose stacks configured.")
                return
            markup = inline_item_keyboard("compose", action, stack_names, row_width=2)
            label = {
                "up": "bring up",
                "down": "bring down",
                "restart": "restart",
                "pull": "pull & recreate",
                "logs": "view logs for",
            }
            bot_inst.send_message(
                chat_id,
                f"Which stack to {label.get(action, action)}?",
                reply_markup=markup,
            )
            return

        # Execute stack action
        if action in ("up", "down", "restart", "pull", "logs") and target:
            stack = _find_stack(config.compose_stacks, target)
            if not stack:
                bot_inst.answer_callback_query(call.id, f"Stack '{target}' not found")
                return

            bot_inst.answer_callback_query(call.id, f"Running {action} on {target}...")

            if action == "up":
                result = stack_up(stack)
            elif action == "down":
                result = stack_down(stack)
            elif action == "restart":
                result = stack_restart(stack)
            elif action == "pull":
                result = stack_pull_recreate(stack)
            elif action == "logs":
                result = stack_logs(stack)
                output = result.get("output", "")
                if output.strip():
                    for chunk_text in chunk_message(escape_html(output)):
                        bot_inst.send_message(chat_id, chunk_text)
                else:
                    bot_inst.send_message(chat_id, "No logs available.")
                return

            icon = "\u2705" if result.get("success") else "\u26a0\ufe0f"
            error = result.get("error", "")
            msg = f"{icon} {action.capitalize()} {target}: {'OK' if result.get('success') else error[:500]}"
            bot_inst.send_message(chat_id, msg)
            return

        bot_inst.answer_callback_query(call.id, "Unknown action")

    register_callback("compose", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_COMPOSE)
    @authorized(config)
    def handle_compose_menu(message):
        _send_compose_menu(message.chat.id)

    @bot.message_handler(commands=["compose"])
    @authorized(config)
    def handle_compose_command(message):
        _send_compose_menu(message.chat.id)
