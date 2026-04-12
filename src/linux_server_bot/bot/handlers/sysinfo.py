"""System info, stress test, and fan control handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telebot.handler_backends import State, StatesGroup

from linux_server_bot.bot.callbacks import register_callback
from linux_server_bot.bot.menus import BTN_FAN, BTN_STRESS, BTN_SYSINFO, inline_action_keyboard
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


class StressTestStates(StatesGroup):
    waiting_for_duration = State()


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register system info, stress test, and fan control handlers."""

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        chat_id = call.message.chat.id

        if action == "cancel":
            bot_inst.answer_callback_query(call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        if action == "fan_off":
            bot_inst.answer_callback_query(call.id, "Setting fans off...")
            result = set_fan_state(0)
            icon = "\U0001f4a8" if result["success"] else "\u26a0\ufe0f"
            msg = "Fans state changed to 0: Off (automatic)." if result["success"] else f"Failed: {result['error']}"
            bot_inst.send_message(chat_id, f"{icon} {msg}")
            return

        if action == "fan_on":
            bot_inst.answer_callback_query(call.id, "Setting fans on...")
            result = set_fan_state(1)
            icon = "\U0001f4a8" if result["success"] else "\u26a0\ufe0f"
            msg = "Fans state changed to 1: On." if result["success"] else f"Failed: {result['error']}"
            bot_inst.send_message(chat_id, f"{icon} {msg}")
            return

        bot_inst.answer_callback_query(call.id, "Unknown action")

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
        else:
            bot.send_message(message.chat.id, "No system info available.")

    @bot.message_handler(commands=["sysinfo"])
    @authorized(config)
    def handle_sysinfo_command(message):
        handle_sysinfo(message)

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
