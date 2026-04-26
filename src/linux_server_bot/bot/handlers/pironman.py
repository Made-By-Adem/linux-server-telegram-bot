"""Pironman 5 / 5 Max handler -- fan modes, RGB LED, fan LED, OLED sleep."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telebot.handler_backends import State, StatesGroup

from linux_server_bot.bot.callbacks import register_callback, safe_answer_callback_query
from linux_server_bot.bot.menus import BTN_PIRONMAN, inline_action_keyboard
from linux_server_bot.shared.actions.pironman import (
    FAN_LED_MODES,
    FAN_MODES,
    LED_STYLES,
    get_config,
    set_fan_led,
    set_fan_mode,
    set_oled_sleep,
    set_rgb_brightness,
    set_rgb_color,
    set_rgb_enabled,
    set_rgb_speed,
    set_rgb_style,
)
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.telegram import escape_html

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_MODULE = "pironman"


class PironmanStates(StatesGroup):
    waiting_for_color = State()
    waiting_for_speed = State()
    waiting_for_brightness = State()
    waiting_for_oled_sleep = State()


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register pironman handlers."""

    def _is_max() -> bool:
        return config.pironman.variant == "max"

    def _send_result(chat_id: int, label: str, result: dict) -> None:
        if result["success"]:
            bot.send_message(chat_id, f"✅ {label}")
        else:
            bot.send_message(chat_id, f"⚠️ {label}: {result['error']}")

    def _main_menu_actions() -> list[tuple[str, str]]:
        actions = [
            ("\U0001f4a8 Fan mode", "fan_menu"),
            ("\U0001f7e2 RGB on", "rgb_on"),
            ("\U0001f534 RGB off", "rgb_off"),
            ("\U0001f3a8 Color", "color"),
            ("\U0001f4ab Style", "style_menu"),
            ("⏩ Speed", "speed"),
            ("\U0001f506 Brightness", "brightness"),
            ("\U0001f4cb Config", "show_config"),
        ]
        if _is_max():
            actions.insert(-1, ("\U0001f4a1 Fan LED", "fan_led_menu"))
            actions.insert(-1, ("\U0001f4f4 OLED sleep", "oled_sleep"))
        return actions

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        chat_id = call.message.chat.id

        if action == "cancel":
            safe_answer_callback_query(bot_inst, call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        if action == "fan_menu":
            safe_answer_callback_query(bot_inst, call.id)
            fan_actions = [(f"\U0001f4a8 {label}", f"fan_{mode}") for mode, label in FAN_MODES.items()]
            markup = inline_action_keyboard(_MODULE, fan_actions, row_width=1)
            bot_inst.send_message(chat_id, "Choose fan mode:", reply_markup=markup)
            return

        if action and action.startswith("fan_") and action != "fan_menu" and action != "fan_led_menu":
            mode = action.replace("fan_", "")
            if mode in FAN_MODES:
                safe_answer_callback_query(bot_inst, call.id, "Setting fan mode...")
                result = set_fan_mode(mode)
                _send_result(chat_id, f"Fan mode set to: {FAN_MODES[mode]}", result)
                return

        if action == "rgb_on":
            safe_answer_callback_query(bot_inst, call.id, "Turning RGB on...")
            result = set_rgb_enabled(True)
            _send_result(chat_id, "RGB turned on", result)
            return

        if action == "rgb_off":
            safe_answer_callback_query(bot_inst, call.id, "Turning RGB off...")
            result = set_rgb_enabled(False)
            _send_result(chat_id, "RGB turned off", result)
            return

        if action == "color":
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.send_message(chat_id, "Send a HEX color code (e.g. FF0000 or #00AABB):")
            bot.set_state(call.from_user.id, PironmanStates.waiting_for_color, chat_id)
            return

        if action == "style_menu":
            safe_answer_callback_query(bot_inst, call.id)
            style_actions = [(s, f"style_{s}") for s in LED_STYLES]
            markup = inline_action_keyboard(_MODULE, style_actions, row_width=2)
            bot_inst.send_message(chat_id, "Choose LED style:", reply_markup=markup)
            return

        if action and action.startswith("style_"):
            style = action.replace("style_", "")
            if style in LED_STYLES:
                safe_answer_callback_query(bot_inst, call.id, f"Setting style {style}...")
                result = set_rgb_style(style)
                _send_result(chat_id, f"LED style set to: {style}", result)
                return

        if action == "speed":
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.send_message(chat_id, "Enter LED speed (0-100):")
            bot.set_state(call.from_user.id, PironmanStates.waiting_for_speed, chat_id)
            return

        if action == "brightness":
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.send_message(chat_id, "Enter LED brightness (0-100):")
            bot.set_state(call.from_user.id, PironmanStates.waiting_for_brightness, chat_id)
            return

        if action == "fan_led_menu" and _is_max():
            safe_answer_callback_query(bot_inst, call.id)
            fan_led_actions = [(f"\U0001f4a1 {m.capitalize()}", f"fanled_{m}") for m in FAN_LED_MODES]
            markup = inline_action_keyboard(_MODULE, fan_led_actions, row_width=3)
            bot_inst.send_message(chat_id, "Choose fan LED mode:", reply_markup=markup)
            return

        if action and action.startswith("fanled_") and _is_max():
            mode = action.replace("fanled_", "")
            if mode in FAN_LED_MODES:
                safe_answer_callback_query(bot_inst, call.id, f"Setting fan LED {mode}...")
                result = set_fan_led(mode)
                _send_result(chat_id, f"Fan LED set to: {mode}", result)
                return

        if action == "oled_sleep" and _is_max():
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.send_message(chat_id, "Enter OLED sleep timeout in seconds (5-600):")
            bot.set_state(call.from_user.id, PironmanStates.waiting_for_oled_sleep, chat_id)
            return

        if action == "show_config":
            safe_answer_callback_query(bot_inst, call.id, "Loading config...")
            result = get_config()
            text = escape_html(result["output"]) if result["success"] else f"Error: {result['output']}"
            bot_inst.send_message(
                chat_id,
                f"<b>Pironman config:</b>\n<pre>{text}</pre>",
                parse_mode="HTML",
            )
            return

        safe_answer_callback_query(bot_inst, call.id, "Unknown action")

    register_callback(_MODULE, _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_PIRONMAN)
    @authorized(config)
    def handle_pironman_menu(message):
        logger.info("User %s opened pironman menu", message.from_user.first_name)
        markup = inline_action_keyboard(_MODULE, _main_menu_actions(), row_width=2)
        variant = config.pironman.variant.upper()
        bot.send_message(
            message.chat.id,
            f"Pironman 5 {variant} controls:",
            reply_markup=markup,
        )

    # -- State handlers for text input --

    @bot.message_handler(state=PironmanStates.waiting_for_color)
    @authorized(config)
    def handle_color_input(message):
        bot.delete_state(message.from_user.id, message.chat.id)
        result = set_rgb_color(message.text.strip())
        _send_result(message.chat.id, f"Color set to: {message.text.strip()}", result)

    @bot.message_handler(state=PironmanStates.waiting_for_speed)
    @authorized(config)
    def handle_speed_input(message):
        bot.delete_state(message.from_user.id, message.chat.id)
        text = message.text.strip()
        if not text.isdigit():
            bot.send_message(message.chat.id, "Please enter a number between 0 and 100.")
            return
        result = set_rgb_speed(int(text))
        _send_result(message.chat.id, f"LED speed set to: {text}", result)

    @bot.message_handler(state=PironmanStates.waiting_for_brightness)
    @authorized(config)
    def handle_brightness_input(message):
        bot.delete_state(message.from_user.id, message.chat.id)
        text = message.text.strip()
        if not text.isdigit():
            bot.send_message(message.chat.id, "Please enter a number between 0 and 100.")
            return
        result = set_rgb_brightness(int(text))
        _send_result(message.chat.id, f"LED brightness set to: {text}", result)

    @bot.message_handler(state=PironmanStates.waiting_for_oled_sleep)
    @authorized(config)
    def handle_oled_sleep_input(message):
        bot.delete_state(message.from_user.id, message.chat.id)
        text = message.text.strip()
        if not text.isdigit():
            bot.send_message(message.chat.id, "Please enter a number between 5 and 600.")
            return
        result = set_oled_sleep(int(text))
        _send_result(message.chat.id, f"OLED sleep set to: {text}s", result)
