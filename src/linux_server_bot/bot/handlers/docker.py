"""Docker container management handlers."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback
from linux_server_bot.bot.menus import (
    BTN_DOCKER,
    inline_action_keyboard,
    inline_item_keyboard,
)
from linux_server_bot.config import MonitoredItem, update_monitoring_policy
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
    ("\U0001f6e1 Policy", "policy"),
]

_POLICY_LABELS = {
    "ignore": "\U0001f6ab Ignore",
    "notify": "\U0001f514 Notify",
    "notify_restart": "\U0001f504 Notify + Restart",
}

_POLICY_ICONS = {
    "ignore": "\U0001f6ab",
    "notify": "\U0001f514",
    "notify_restart": "\U0001f504",
}


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


def _get_config_path() -> str:
    return os.environ.get("CONFIG_PATH", "config.yaml")


def _send_policy_overview(bot, chat_id: int, config) -> None:
    """Show current monitoring policies for all auto-detected containers."""
    all_containers = get_container_names()
    if not all_containers:
        bot.send_message(chat_id, "No Docker containers detected.")
        return

    lines = ["<b>Monitoring policies (containers):</b>", ""]
    for name in all_containers:
        policy = config.monitoring.get_container_policy(name)
        icon = _POLICY_ICONS.get(policy, "?")
        lines.append(f"{icon} <b>{name}</b>: {policy}")

    lines.append("\nTap a container below to change its policy:")
    markup = inline_item_keyboard("docker", "policy_pick", all_containers, row_width=2)
    bot.send_message(chat_id, "\n".join(lines), reply_markup=markup, parse_mode="HTML")


def _send_policy_choice(bot, chat_id: int, container_name: str) -> None:
    """Show policy options for a specific container."""
    from telebot import types

    markup = types.InlineKeyboardMarkup(row_width=1)
    for action_value in MonitoredItem.ACTIONS:
        label = _POLICY_LABELS[action_value]
        markup.add(
            types.InlineKeyboardButton(
                label,
                callback_data=f"docker:policy_set:{container_name}:{action_value}",
            )
        )
    markup.add(
        types.InlineKeyboardButton(
            "\u274c Cancel",
            callback_data="docker:cancel",
        )
    )
    bot.send_message(
        chat_id,
        f"Choose monitoring policy for <b>{container_name}</b>:",
        reply_markup=markup,
        parse_mode="HTML",
    )


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register Docker container management handlers."""

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
            _send_status(bot_inst, chat_id)
            return

        # -- Policy management --
        if action == "policy":
            bot_inst.answer_callback_query(call.id)
            _send_policy_overview(bot_inst, chat_id, config)
            return

        if action == "policy_pick" and target:
            bot_inst.answer_callback_query(call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            _send_policy_choice(bot_inst, chat_id, target)
            return

        if action == "policy_set" and target:
            # parts = ["policy_set", container_name, new_policy]
            new_policy = parts[2] if len(parts) > 2 else None
            if new_policy and new_policy in MonitoredItem.ACTIONS:
                bot_inst.answer_callback_query(call.id, f"Setting {target} to {new_policy}...")
                update_monitoring_policy("containers", target, new_policy, _get_config_path())
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                icon = _POLICY_ICONS.get(new_policy, "")
                bot_inst.send_message(
                    chat_id,
                    f"{icon} Policy for <b>{target}</b> set to <b>{new_policy}</b>.",
                    parse_mode="HTML",
                )
            else:
                bot_inst.answer_callback_query(call.id, "Invalid policy")
            return

        # -- Container management --
        # Single-container actions requiring target selection
        if action in ("start", "stop", "restart") and not target:
            bot_inst.answer_callback_query(call.id)
            containers = get_container_names()
            if not containers:
                bot_inst.send_message(chat_id, "No containers found.")
                return
            markup = inline_item_keyboard("docker", action, containers, row_width=2)
            bot_inst.send_message(chat_id, f"Which container to {action}?", reply_markup=markup)
            return

        # Execute single-container action
        if action in ("start", "stop", "restart") and target:
            bot_inst.answer_callback_query(call.id, f"{action.capitalize()}ing {target}...")
            result = container_action(action, target)
            icon = "\u2705" if result["success"] else "\u26a0\ufe0f"
            msg = f"{icon} {action.capitalize()} {target}: {'OK' if result['success'] else result['error']}"
            bot_inst.send_message(chat_id, msg)
            _send_status(bot_inst, chat_id)
            return

        # All-container actions
        if action in ("start_all", "stop_all", "restart_all"):
            real_action = action.replace("_all", "")
            bot_inst.answer_callback_query(call.id, f"{real_action.capitalize()}ing all containers...")
            results = container_action_all(real_action)
            failures = [r for r in results if not r["success"]]
            if failures:
                lines = [f"\u26a0\ufe0f {r['name']}: {r['error']}" for r in failures]
                bot_inst.send_message(chat_id, "\n".join(lines))
            _send_status(bot_inst, chat_id)
            return

        bot_inst.answer_callback_query(call.id, "Unknown action")

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
