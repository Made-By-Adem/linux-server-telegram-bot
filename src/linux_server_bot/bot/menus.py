"""Keyboard and menu builder helpers for the Telegram bot."""

from __future__ import annotations

from typing import TYPE_CHECKING

from telebot import types

if TYPE_CHECKING:
    from linux_server_bot.config import AppConfig

# Button labels used across handlers -- single source of truth
BTN_WOL = "\U0001f4bb Wake up WoL"
BTN_SERVICES = "\U0001f4e6 Services"
BTN_DOCKER = "\U0001f433   Docker"
BTN_COMPOSE = "\U0001f6a2 Compose"
BTN_LOGS = "\U0001f4dc       Logs"
BTN_COMMAND = "\U0001f4e4 Send command"
BTN_SERVERS = "\U0001f514 Check servers"
BTN_SYSINFO = "\U0001f4c3 System info"
BTN_STRESS = "\U0001f4aa Stress test"
BTN_FAN = "\U0001f4a8 Fan state"
BTN_SECURITY = "\U0001f512 Security"
BTN_UPDATES = "\U0001f504 Updates"
BTN_BACKUPS = "\U0001f4be Backups"
BTN_REBOOT = "\U0001f501 Reboot"
BTN_BACK_MAIN = "\U0001f519 Go back to main"
BTN_BACK_SERVICES = "\U0001f519 Go back to services"
BTN_BACK_DOCKER = "\U0001f519 Go back to docker"
BTN_BACK_COMPOSE = "\U0001f519 Go back to compose"

# Feature flag -> button label mapping
_FEATURE_BUTTONS: list[tuple[str, str]] = [
    ("wol", BTN_WOL),
    ("systemd_services", BTN_SERVICES),
    ("docker_containers", BTN_DOCKER),
    ("docker_compose", BTN_COMPOSE),
    ("logs", BTN_LOGS),
    ("custom_commands", BTN_COMMAND),
    ("server_ping", BTN_SERVERS),
    ("system_info", BTN_SYSINFO),
    ("stress_test", BTN_STRESS),
    ("fan_control", BTN_FAN),
    ("security_overview", BTN_SECURITY),
    ("container_updates", BTN_UPDATES),
    ("backups", BTN_BACKUPS),
    ("reboot", BTN_REBOOT),
]


def build_main_menu(config: AppConfig) -> types.ReplyKeyboardMarkup:
    """Build the main menu keyboard, hiding disabled features."""
    markup = types.ReplyKeyboardMarkup(row_width=4, one_time_keyboard=True)
    buttons = []
    for feature_name, label in _FEATURE_BUTTONS:
        if getattr(config.features, feature_name, True):
            buttons.append(types.KeyboardButton(label))
    if buttons:
        markup.add(*buttons)
    return markup


def build_item_keyboard(
    items: list[str],
    prefix: str,
    back_button: str = BTN_BACK_MAIN,
    row_width: int = 3,
) -> types.ReplyKeyboardMarkup:
    """Build a keyboard with one button per item plus a back button.

    Example: build_item_keyboard(["nginx", "docker"], "⏯ Start service:")
    -> buttons: ["⏯ Start service: nginx", "⏯ Start service: docker", "🔙 Go back"]
    """
    markup = types.ReplyKeyboardMarkup(row_width=row_width, one_time_keyboard=True)
    for item in items:
        markup.add(types.KeyboardButton(f"{prefix} {item}"))
    markup.add(types.KeyboardButton(back_button))
    return markup


def build_action_keyboard(
    actions: list[str],
    back_button: str = BTN_BACK_MAIN,
    row_width: int = 3,
) -> types.ReplyKeyboardMarkup:
    """Build a keyboard from a list of action labels plus a back button."""
    markup = types.ReplyKeyboardMarkup(row_width=row_width, one_time_keyboard=True)
    buttons = [types.KeyboardButton(a) for a in actions]
    buttons.append(types.KeyboardButton(back_button))
    markup.add(*buttons)
    return markup


def build_confirm_keyboard(
    confirm_text: str,
    cancel_text: str,
    row_width: int = 2,
) -> types.ReplyKeyboardMarkup:
    """Build a simple confirm/cancel keyboard."""
    markup = types.ReplyKeyboardMarkup(row_width=row_width, one_time_keyboard=True)
    markup.add(
        types.KeyboardButton(confirm_text),
        types.KeyboardButton(cancel_text),
    )
    return markup
