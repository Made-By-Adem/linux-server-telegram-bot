"""Settings handler -- toggle features on/off from Telegram."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from telebot import types

from linux_server_bot.bot.callbacks import register_callback, safe_answer_callback_query
from linux_server_bot.bot.menus import BTN_SETTINGS
from linux_server_bot.config import FeaturesConfig, update_feature
from linux_server_bot.shared.auth import authorized

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

# Human-readable labels for features
_FEATURE_LABELS = {
    "systemd_services": "Services",
    "docker_containers": "Docker",
    "docker_compose": "Compose",
    "custom_commands": "Commands",
    "wol": "Wake-on-LAN",
    "security_overview": "Security",
    "backups": "Backups",
    "container_updates": "Updates",
    "logs": "Logs",
    "server_ping": "Server ping",
    "system_info": "System info",
    "stress_test": "Stress test",
    "fan_control": "Fan control",
    "pironman": "Pironman",
    "reboot": "Reboot",
    "custom_scripts": "Scripts",
    "settings": "Settings",
}


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register settings handlers."""

    def _get_config_path() -> str:
        return os.environ.get("CONFIG_PATH", "config/config.yaml")

    def _send_settings(bot_inst, chat_id: int) -> None:
        """Show all features with their current state and toggle buttons."""
        markup = types.InlineKeyboardMarkup(row_width=1)

        for feature_name in FeaturesConfig.__dataclass_fields__:
            # Don't allow disabling settings itself
            if feature_name == "settings":
                continue
            enabled = getattr(config.features, feature_name, True)
            icon = "\u2705" if enabled else "\u274c"
            label = _FEATURE_LABELS.get(feature_name, feature_name)
            new_state = "off" if enabled else "on"
            markup.add(
                types.InlineKeyboardButton(
                    f"{icon} {label}",
                    callback_data=f"settings:toggle:{feature_name}:{new_state}",
                )
            )

        markup.add(types.InlineKeyboardButton("\u274c Close", callback_data="settings:cancel"))
        bot_inst.send_message(
            chat_id,
            "<b>Feature settings:</b>\nTap to toggle on/off. Changes take effect immediately.",
            reply_markup=markup,
            parse_mode="HTML",
        )

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        chat_id = call.message.chat.id

        if action == "cancel":
            safe_answer_callback_query(bot_inst, call.id, "Closed")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        if action == "toggle" and len(parts) >= 3:
            feature_name = parts[1]
            new_state = parts[2] == "on"
            label = _FEATURE_LABELS.get(feature_name, feature_name)

            try:
                update_feature(feature_name, new_state, _get_config_path())
                safe_answer_callback_query(bot_inst, call.id, f"{label}: {'on' if new_state else 'off'}")

                # Refresh the settings menu in-place
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                _send_settings(bot_inst, chat_id)

                # Re-send the main menu so button changes take effect
                show_menu(call.message)
            except ValueError as e:
                safe_answer_callback_query(bot_inst, call.id, str(e))
            return

        safe_answer_callback_query(bot_inst, call.id, "Unknown action")

    register_callback("settings", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_SETTINGS)
    @authorized(config)
    def handle_settings_menu(message):
        _send_settings(bot, message.chat.id)

    @bot.message_handler(commands=["settings"])
    @authorized(config)
    def handle_settings_command(message):
        _send_settings(bot, message.chat.id)
