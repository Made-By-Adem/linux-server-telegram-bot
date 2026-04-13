"""Keyboard and menu builder helpers for the Telegram bot.

Main menu uses a persistent ReplyKeyboard (always visible at the bottom).
Submenu actions use InlineKeyboard (embedded in messages, callback-based).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from telebot import types

if TYPE_CHECKING:
    from linux_server_bot.config import AppConfig

# ---------------------------------------------------------------------------
# Button labels used by handlers -- single source of truth
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Main menu -- persistent ReplyKeyboard
# ---------------------------------------------------------------------------


def build_main_menu(config: AppConfig) -> types.ReplyKeyboardMarkup:
    """Build the main menu keyboard, hiding disabled features.

    Uses ``resize_keyboard=True`` so it stays compact and persistent
    (no ``one_time_keyboard``).
    """
    markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    buttons = []
    for feature_name, label in _FEATURE_BUTTONS:
        if getattr(config.features, feature_name, True):
            buttons.append(types.KeyboardButton(label))
    if buttons:
        markup.add(*buttons)
    return markup


# ---------------------------------------------------------------------------
# Inline keyboards -- used inside messages for submenu actions
# ---------------------------------------------------------------------------


def inline_action_keyboard(
    module: str,
    actions: list[tuple[str, str]],
    row_width: int = 3,
) -> types.InlineKeyboardMarkup:
    """Build an InlineKeyboard for a module's action menu.

    *actions* is a list of ``(label, action_name)`` tuples.
    ``callback_data`` format: ``"module:action"``
    e.g. ``[("Start", "start"), ("Stop", "stop")]`` with module ``"docker"``
    produces callbacks ``"docker:start"``, ``"docker:stop"``.
    """
    markup = types.InlineKeyboardMarkup(row_width=row_width)
    buttons = [types.InlineKeyboardButton(label, callback_data=f"{module}:{action}") for label, action in actions]
    # Add in rows
    for i in range(0, len(buttons), row_width):
        markup.add(*buttons[i : i + row_width])
    return markup


def inline_item_keyboard(
    module: str,
    action: str,
    items: list[str],
    row_width: int = 2,
) -> types.InlineKeyboardMarkup:
    """Build an InlineKeyboard to select an item.

    ``callback_data`` format: ``"module:action:item"``
    e.g. ``inline_item_keyboard("docker", "start", ["nginx", "redis"])``
    produces ``"docker:start:nginx"`` and ``"docker:start:redis"``.

    A cancel button is appended automatically.
    """
    markup = types.InlineKeyboardMarkup(row_width=row_width)
    buttons = [types.InlineKeyboardButton(name, callback_data=f"{module}:{action}:{name}") for name in items]
    for i in range(0, len(buttons), row_width):
        markup.add(*buttons[i : i + row_width])
    markup.add(
        types.InlineKeyboardButton("\u274c Cancel", callback_data=f"{module}:cancel"),
    )
    return markup


def inline_confirm_keyboard(
    module: str,
    action: str,
    target: str = "",
) -> types.InlineKeyboardMarkup:
    """Build a confirm / cancel InlineKeyboard.

    ``callback_data``:
    - confirm: ``"module:action:target:confirm"`` (or ``"module:action:confirm"`` if no target)
    - cancel:  ``"module:action:target:cancel"``  (or ``"module:action:cancel"``)
    """
    base = f"{module}:{action}:{target}" if target else f"{module}:{action}"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("\u2705 Confirm", callback_data=f"{base}:confirm"),
        types.InlineKeyboardButton("\u274c Cancel", callback_data=f"{base}:cancel"),
    )
    return markup
