"""System info, stress test, fan control, and threshold handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telebot.handler_backends import State, StatesGroup

from linux_server_bot.bot.callbacks import register_callback, safe_answer_callback_query
from linux_server_bot.bot.menus import BTN_FAN, BTN_STRESS, BTN_SYSINFO, inline_action_keyboard
from linux_server_bot.config import THRESHOLD_KEYS, update_monitoring_threshold
from linux_server_bot.shared.actions.sysinfo import get_sysinfo_text, run_stress_test, set_fan_state
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.telegram import chunk_message, escape_html

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_FAN_ACTIONS = [
    ("\U0001f4a8 Off (auto)", "fan_off"),
    ("\U0001f4a8 On", "fan_on"),
]

_THRESHOLD_LABELS = {
    "cpu_percent": ("\U0001f5a5 CPU", "%"),
    "storage_percent": ("\U0001f4be Disk", "%"),
    "temperature_celsius": ("\U0001f321\ufe0f Temp", "\u00b0C"),
}


class StressTestStates(StatesGroup):
    waiting_for_duration = State()


class ThresholdStates(StatesGroup):
    waiting_for_value = State()


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register system info, stress test, fan control, and threshold handlers."""

    def _send_thresholds(bot_inst, chat_id: int) -> None:
        """Show current thresholds with buttons to change them."""
        from telebot import types

        lines = ["<b>Monitoring thresholds:</b>\n"]
        for key, (label, unit) in _THRESHOLD_LABELS.items():
            val = config.monitoring.thresholds.get(key, "?")
            lines.append(f"{label}: <b>{val}{unit}</b>")

        markup = types.InlineKeyboardMarkup(row_width=1)
        for key, (label, unit) in _THRESHOLD_LABELS.items():
            val = config.monitoring.thresholds.get(key, "?")
            markup.add(
                types.InlineKeyboardButton(
                    f"{label}: {val}{unit}",
                    callback_data=f"sysinfo:threshold_pick:{key}",
                )
            )
        markup.add(types.InlineKeyboardButton("\u274c Cancel", callback_data="sysinfo:cancel"))

        bot_inst.send_message(
            chat_id,
            "\n".join(lines) + "\n\nTap a threshold to change it:",
            reply_markup=markup,
            parse_mode="HTML",
        )

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        chat_id = call.message.chat.id

        if action == "cancel":
            safe_answer_callback_query(bot_inst, call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        if action == "fan_off":
            safe_answer_callback_query(bot_inst, call.id, "Setting fans off...")
            result = set_fan_state(0)
            icon = "\U0001f4a8" if result["success"] else "\u26a0\ufe0f"
            msg = "Fans state changed to 0: Off (automatic)." if result["success"] else f"Failed: {result['error']}"
            bot_inst.send_message(chat_id, f"{icon} {msg}")
            return

        if action == "fan_on":
            safe_answer_callback_query(bot_inst, call.id, "Setting fans on...")
            result = set_fan_state(1)
            icon = "\U0001f4a8" if result["success"] else "\u26a0\ufe0f"
            msg = "Fans state changed to 1: On." if result["success"] else f"Failed: {result['error']}"
            bot_inst.send_message(chat_id, f"{icon} {msg}")
            return

        if action == "thresholds":
            safe_answer_callback_query(bot_inst, call.id)
            _send_thresholds(bot_inst, chat_id)
            return

        if action == "threshold_pick":
            key = parts[1] if len(parts) > 1 else None
            if key and key in THRESHOLD_KEYS:
                safe_answer_callback_query(bot_inst, call.id)
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                label, unit = _THRESHOLD_LABELS[key]
                lo, hi = THRESHOLD_KEYS[key]
                current = config.monitoring.thresholds.get(key, "?")
                bot_inst.send_message(
                    chat_id,
                    f"Current {label} threshold: <b>{current}{unit}</b>\nEnter a new value ({lo}-{hi}):",
                    parse_mode="HTML",
                )
                bot.set_state(call.from_user.id, ThresholdStates.waiting_for_value, chat_id)
                with bot.retrieve_data(call.from_user.id, chat_id) as data:
                    data["threshold_key"] = key
            else:
                safe_answer_callback_query(bot_inst, call.id, "Unknown threshold")
            return

        safe_answer_callback_query(bot_inst, call.id, "Unknown action")

    register_callback("sysinfo", _handle_callback)

    # --- System Info ---
    @bot.message_handler(func=lambda m: m.text == BTN_SYSINFO)
    @authorized(config)
    def handle_sysinfo(message):
        logger.info("User %s requested system info", message.from_user.first_name)
        bot.reply_to(message, "Getting system info...")
        text = get_sysinfo_text()
        if text.strip():
            output = "<b>System info:</b>\n" + escape_html(text)
            for chunk in chunk_message(output):
                bot.send_message(message.chat.id, chunk, parse_mode="HTML")
        # Show thresholds button after sysinfo
        markup = inline_action_keyboard(
            "sysinfo",
            [("\U0001f4ca Thresholds", "thresholds")],
            row_width=1,
        )
        bot.send_message(message.chat.id, "Manage monitoring thresholds:", reply_markup=markup)

    @bot.message_handler(commands=["sysinfo"])
    @authorized(config)
    def handle_sysinfo_command(message):
        handle_sysinfo(message)

    # --- Threshold value input ---
    @bot.message_handler(state=ThresholdStates.waiting_for_value)
    @authorized(config)
    def handle_threshold_input(message):
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            key = data.get("threshold_key")
        bot.delete_state(message.from_user.id, message.chat.id)

        if not key or key not in THRESHOLD_KEYS:
            bot.send_message(message.chat.id, "Something went wrong. Try again.")
            return

        text = message.text.strip()
        try:
            value = int(text)
        except ValueError:
            try:
                value = float(text)
            except ValueError:
                bot.send_message(message.chat.id, "Please enter a valid number.")
                return

        lo, hi = THRESHOLD_KEYS[key]
        if not (lo <= value <= hi):
            bot.send_message(message.chat.id, f"Value must be between {lo} and {hi}.")
            return

        try:
            update_monitoring_threshold(key, value)
            label, unit = _THRESHOLD_LABELS[key]
            bot.send_message(
                message.chat.id,
                f"\u2705 {label} threshold set to <b>{value}{unit}</b>.",
                parse_mode="HTML",
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"Failed to update threshold: {e}")

    # --- Stress Test (StatesGroup for duration input) ---
    @bot.message_handler(func=lambda m: m.text == BTN_STRESS)
    @authorized(config)
    def handle_stress_menu(message):
        bot.send_message(message.chat.id, "Enter the number of minutes for the stress test:")
        bot.set_state(message.from_user.id, StressTestStates.waiting_for_duration, message.chat.id)

    @bot.message_handler(state=StressTestStates.waiting_for_duration)
    @authorized(config)
    def handle_stress_input(message):
        bot.delete_state(message.from_user.id, message.chat.id)
        text = message.text.strip()
        if not text.isdigit() or int(text) <= 0:
            bot.send_message(message.chat.id, "Please enter a valid number greater than 0.")
            return
        minutes = int(text)
        bot.send_message(message.chat.id, f"Stress test started for {minutes} minutes.")
        logger.info("User %s started stress test for %d minutes", message.from_user.first_name, minutes)
        result = run_stress_test(minutes)
        bot.send_message(message.chat.id, f"Stress test finished.\n{result.get('output', '')}")

    # --- Fan Control ---
    @bot.message_handler(func=lambda m: m.text == BTN_FAN)
    @authorized(config)
    def handle_fan_menu(message):
        logger.info("User %s requested fan state", message.from_user.first_name)
        markup = inline_action_keyboard("sysinfo", _FAN_ACTIONS, row_width=2)
        bot.send_message(message.chat.id, "Choose fan state:", reply_markup=markup)
