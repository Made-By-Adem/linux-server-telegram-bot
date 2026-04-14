"""Docker container management handlers."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback, safe_answer_callback_query
from linux_server_bot.bot.menus import (
    BTN_DOCKER,
    inline_action_keyboard,
    inline_item_keyboard,
)
from linux_server_bot.config import MonitoredItem, update_monitoring_policy
from linux_server_bot.shared.actions.docker import (
    container_action,
    container_action_all,
    get_container_statuses,
    resolve_container_patterns,
)
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.telegram import send_loading

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


def _get_status_text(config) -> str:
    """Build status text for configured containers."""
    resolved = resolve_container_patterns(config.containers)
    if not resolved:
        return "No containers configured. Add containers to config.yaml."

    all_statuses = get_container_statuses()
    status_map = {s.name: s for s in all_statuses}

    lines = ["<b>Status containers:</b>"]
    for item in resolved:
        s = status_map.get(item.name)
        if s:
            icon = "\u2705" if s.running else "\u274c"
            lines.append(f"{icon} {s.name}: {s.status}")
        else:
            lines.append(f"\u2753 {item.name}: not found on server")
    return "\n".join(lines)


def _send_status(bot, chat_id: int, config) -> None:
    """Show status of configured containers."""
    bot.send_message(chat_id, _get_status_text(config), parse_mode="HTML")


def _get_config_path() -> str:
    return os.environ.get("CONFIG_PATH", "config.yaml")


def _send_policy_overview(bot, chat_id: int, config) -> None:
    """Show current monitoring policies for all configured containers."""
    resolved = resolve_container_patterns(config.containers)
    if not resolved:
        bot.send_message(chat_id, "No containers configured. Add containers to config.yaml.")
        return

    container_names = [item.name for item in resolved]
    lines = ["<b>Monitoring policies (containers):</b>", ""]
    for item in resolved:
        icon = _POLICY_ICONS.get(item.on_failure, "?")
        lines.append(f"{icon} <b>{item.name}</b>: {item.on_failure}")

    lines.append("\nTap a container below to change its policy:")
    markup = inline_item_keyboard("docker", "policy_pick", container_names, row_width=2)
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
            safe_answer_callback_query(bot_inst, call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        if action == "status":
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_text("\U0001f504 Docker status...", chat_id, call.message.message_id)
            text = _get_status_text(config)
            bot_inst.edit_message_text(text, chat_id, call.message.message_id, parse_mode="HTML")
            return

        # -- Policy management --
        if action == "policy":
            safe_answer_callback_query(bot_inst, call.id)
            _send_policy_overview(bot_inst, chat_id, config)
            return

        if action == "policy_pick" and target:
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            _send_policy_choice(bot_inst, chat_id, target)
            return

        if action == "policy_set" and target:
            # parts = ["policy_set", container_name, new_policy]
            new_policy = parts[2] if len(parts) > 2 else None
            if new_policy and new_policy in MonitoredItem.ACTIONS:
                safe_answer_callback_query(bot_inst, call.id, f"Setting {target} to {new_policy}...")
                update_monitoring_policy("containers", target, new_policy, _get_config_path())
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                icon = _POLICY_ICONS.get(new_policy, "")
                bot_inst.send_message(
                    chat_id,
                    f"{icon} Policy for <b>{target}</b> set to <b>{new_policy}</b>.",
                    parse_mode="HTML",
                )
            else:
                safe_answer_callback_query(bot_inst, call.id, "Invalid policy")
            return

        # -- Container management --
        resolved = resolve_container_patterns(config.containers)
        container_names = [item.name for item in resolved]

        if action in ("start", "stop", "restart") and not target:
            safe_answer_callback_query(bot_inst, call.id)
            if not container_names:
                bot_inst.send_message(chat_id, "No containers configured.")
                return
            markup = inline_item_keyboard("docker", action, container_names, row_width=2)
            bot_inst.send_message(chat_id, f"Which container to {action}?", reply_markup=markup)
            return

        # Execute single-container action
        if action in ("start", "stop", "restart") and target:
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_text(
                f"\U0001f504 {action.capitalize()}ing {target}...", chat_id, call.message.message_id
            )
            result = container_action(action, target)
            icon = "\u2705" if result["success"] else "\u26a0\ufe0f"
            msg = f"{icon} {action.capitalize()} {target}: {'OK' if result['success'] else result['error']}"
            bot_inst.edit_message_text(msg, chat_id, call.message.message_id)
            _send_status(bot_inst, chat_id, config)
            return

        # All-container actions
        if action in ("start_all", "stop_all", "restart_all"):
            real_action = action.replace("_all", "")
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_text(
                f"\U0001f504 {real_action.capitalize()}ing all containers...", chat_id, call.message.message_id
            )
            results = container_action_all(real_action, container_names)
            failures = [r for r in results if not r["success"]]
            if failures:
                lines = [f"\u26a0\ufe0f {r['name']}: {r['error']}" for r in failures]
                bot_inst.send_message(chat_id, "\n".join(lines))
            _send_status(bot_inst, chat_id, config)
            return

        safe_answer_callback_query(bot_inst, call.id, "Unknown action")

    register_callback("docker", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_DOCKER)
    @authorized(config)
    def handle_docker_menu(message):
        import time as _t

        t0 = _t.monotonic()
        loading = send_loading(bot, message.chat.id, "Docker")
        t1 = _t.monotonic()
        text = _get_status_text(config)
        t2 = _t.monotonic()
        bot.edit_message_text(text, message.chat.id, loading.message_id, parse_mode="HTML")
        t3 = _t.monotonic()
        _send_docker_menu(bot, message.chat.id)
        t4 = _t.monotonic()
        logger.info(
            "TIMING docker_menu: send_loading=%.2fs get_status=%.2fs edit_msg=%.2fs send_menu=%.2fs total=%.2fs",
            t1 - t0,
            t2 - t1,
            t3 - t2,
            t4 - t3,
            t4 - t0,
        )

    @bot.message_handler(commands=["docker"])
    @authorized(config)
    def handle_docker_command(message):
        handle_docker_menu(message)
