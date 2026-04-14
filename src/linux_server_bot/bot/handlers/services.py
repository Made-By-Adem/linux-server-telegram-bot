"""Systemd service management handlers."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback, safe_answer_callback_query
from linux_server_bot.bot.menus import (
    BTN_SERVICES,
    inline_action_keyboard,
    inline_item_keyboard,
)
from linux_server_bot.config import MonitoredItem, update_monitoring_policy
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


def _send_services_menu(bot, chat_id: int) -> None:
    markup = inline_action_keyboard("services", _ACTIONS, row_width=3)
    bot.send_message(chat_id, "What do you want to do?", reply_markup=markup)


def _get_status_text(services: list[str]) -> str:
    """Build status text for configured services."""
    if not services:
        return "No services configured. Add services to config.yaml."

    statuses = get_service_statuses(services)
    lines = ["<b>Status services:</b>"]
    for s in statuses:
        icon = "\u2705" if s.active else "\u274c"
        lines.append(f"{icon} {s.name}: {s.state}")
    return "\n".join(lines)


def _send_status(bot, chat_id: int, services: list[str]) -> None:
    bot.send_message(chat_id, _get_status_text(services), parse_mode="HTML")


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register all service management handlers."""

    def _get_config_path() -> str:
        return os.environ.get("CONFIG_PATH", "config.yaml")

    def _send_policy_overview(bot_inst, chat_id: int) -> None:
        """Show current monitoring policies for all configured services."""
        service_names = config.get_service_names()
        if not service_names:
            bot_inst.send_message(chat_id, "No services configured. Add services to config.yaml.")
            return

        lines = ["<b>Monitoring policies (services):</b>", ""]
        for name in service_names:
            policy = config.get_service_policy(name)
            icon = _POLICY_ICONS.get(policy, "?")
            lines.append(f"{icon} <b>{name}</b>: {policy}")

        lines.append("\nTap a service below to change its policy:")
        markup = inline_item_keyboard("services", "policy_pick", service_names, row_width=2)
        bot_inst.send_message(chat_id, "\n".join(lines), reply_markup=markup, parse_mode="HTML")

    def _send_policy_choice(bot_inst, chat_id: int, service_name: str) -> None:
        """Show policy options for a specific service."""
        from telebot import types

        markup = types.InlineKeyboardMarkup(row_width=1)
        for action_value in MonitoredItem.ACTIONS:
            label = _POLICY_LABELS[action_value]
            markup.add(
                types.InlineKeyboardButton(
                    label,
                    callback_data=f"services:policy_set:{service_name}:{action_value}",
                )
            )
        markup.add(
            types.InlineKeyboardButton(
                "\u274c Cancel",
                callback_data="services:cancel",
            )
        )
        bot_inst.send_message(
            chat_id,
            f"Choose monitoring policy for <b>{service_name}</b>:",
            reply_markup=markup,
            parse_mode="HTML",
        )

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
            bot_inst.send_chat_action(chat_id, "typing")
            bot_inst.edit_message_text("\U0001f504 Fetching service status...", chat_id, call.message.message_id)
            text = _get_status_text(config.get_service_names())
            bot_inst.edit_message_text(text, chat_id, call.message.message_id, parse_mode="HTML")
            return

        # -- Policy management --
        if action == "policy":
            safe_answer_callback_query(bot_inst, call.id)
            _send_policy_overview(bot_inst, chat_id)
            return

        if action == "policy_pick" and target:
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            _send_policy_choice(bot_inst, chat_id, target)
            return

        if action == "policy_set" and target:
            # parts = ["policy_set", service_name, new_policy]
            new_policy = parts[2] if len(parts) > 2 else None
            if new_policy and new_policy in MonitoredItem.ACTIONS:
                safe_answer_callback_query(bot_inst, call.id, f"Setting {target} to {new_policy}...")
                update_monitoring_policy("services", target, new_policy, _get_config_path())
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

        # -- Service management --
        service_names = config.get_service_names()

        if action in ("start", "stop", "restart") and not target:
            safe_answer_callback_query(bot_inst, call.id)
            if not service_names:
                bot_inst.send_message(chat_id, "No services configured.")
                return
            markup = inline_item_keyboard("services", action, service_names, row_width=2)
            bot_inst.send_message(chat_id, f"Which service to {action}?", reply_markup=markup)
            return

        if action in ("start", "stop", "restart") and target:
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            bot_inst.send_chat_action(chat_id, "typing")
            bot_inst.send_message(chat_id, f"\U0001f504 {action.capitalize()}ing <b>{target}</b>...", parse_mode="HTML")
            result = service_action(action, target)
            icon = "\u2705" if result["success"] else "\u26a0\ufe0f"
            msg = f"{icon} {action.capitalize()} {target}: {'OK' if result['success'] else result['error']}"
            bot_inst.send_message(chat_id, msg)
            _send_status(bot_inst, chat_id, service_names)
            return

        if action in ("start_all", "stop_all", "restart_all"):
            real_action = action.replace("_all", "")
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            bot_inst.send_chat_action(chat_id, "typing")
            bot_inst.send_message(chat_id, f"\U0001f504 {real_action.capitalize()}ing all services...")
            results = service_action_all(real_action, service_names)
            failures = [r for r in results if not r["success"]]
            if failures:
                lines = [f"\u26a0\ufe0f {r['name']}: {r['error']}" for r in failures]
                bot_inst.send_message(chat_id, "\n".join(lines))
            _send_status(bot_inst, chat_id, service_names)
            return

        safe_answer_callback_query(bot_inst, call.id, "Unknown action")

    register_callback("services", _handle_callback)

    def _show_services(message):
        bot.send_chat_action(message.chat.id, "typing")
        loading = bot.reply_to(message, "\U0001f504 Loading Services...")
        text = _get_status_text(config.get_service_names())
        bot.edit_message_text(text, message.chat.id, loading.message_id, parse_mode="HTML")
        _send_services_menu(bot, message.chat.id)

    @bot.message_handler(func=lambda m: m.text == BTN_SERVICES)
    @authorized(config)
    def handle_services_menu(message):
        _show_services(message)

    @bot.message_handler(commands=["services"])
    @authorized(config)
    def handle_services_command(message):
        _show_services(message)
