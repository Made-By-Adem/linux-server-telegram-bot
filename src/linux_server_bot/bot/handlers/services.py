"""Systemd service management handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.menus import (
    BTN_BACK_MAIN,
    BTN_BACK_SERVICES,
    BTN_SERVICES,
    build_action_keyboard,
    build_item_keyboard,
)
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.shell import run_command

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

# Action menu labels
_BTN_START = "\U0001f7e9 Start a service"
_BTN_RESTART = "\U0001f7e8 Restart a service"
_BTN_STOP = "\U0001f7e5 Stop a service"
_BTN_START_ALL = "\U0001f7e9\U0001f7e9 Start all services"
_BTN_RESTART_ALL = "\U0001f7e8\U0001f7e8 Restart all services"
_BTN_STOP_ALL = "\U0001f7e5\U0001f7e5 Stop all services"
_BTN_STATUS = "\U0001f7eb Get status services"


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register all service management handlers."""

    def _show_services_menu(message):
        actions = [_BTN_START, _BTN_RESTART, _BTN_STOP,
                   _BTN_START_ALL, _BTN_RESTART_ALL, _BTN_STOP_ALL, _BTN_STATUS]
        markup = build_action_keyboard(actions, back_button=BTN_BACK_MAIN, row_width=3)
        bot.send_message(message.chat.id, "What do you want to do?", reply_markup=markup)

    def _get_status(message):
        logger.info("User %s requested service status", message.from_user.first_name)
        status_msg = "<b>Status services:</b>"
        for service in config.services:
            result = run_command(["systemctl", "is-active", service])
            state = result.stdout.strip() or "unknown"
            status_msg += f"\n{service}: {state}"
        bot.send_message(message.chat.id, status_msg, parse_mode="HTML")
        _show_services_menu(message)

    def _service_action(message, action: str, service: str):
        logger.info("User %s requested %s for service %s", message.from_user.first_name, action, service)
        bot.reply_to(message, f"{action.capitalize()}ing {service}...")
        result = run_command(["sudo", "systemctl", action, service])
        if not result.success:
            bot.reply_to(message, f"{action.capitalize()}ing {service} failed: {result.stderr}")
        _get_status(message)

    def _all_service_action(message, action: str):
        logger.info("User %s requested %s all services", message.from_user.first_name, action)
        for service in config.services:
            bot.reply_to(message, f"{action.capitalize()}ing {service}...")
            result = run_command(["sudo", "systemctl", action, service])
            if not result.success:
                bot.reply_to(message, f"{action.capitalize()}ing {service} failed: {result.stderr}")
        _get_status(message)

    # Main services menu
    @bot.message_handler(func=lambda m: m.text == BTN_SERVICES)
    @authorized(config)
    def handle_services_menu(message):
        _show_services_menu(message)

    @bot.message_handler(func=lambda m: m.text and m.text.startswith(BTN_BACK_SERVICES))
    @authorized(config)
    def handle_services_back(message):
        _show_services_menu(message)

    @bot.message_handler(commands=["services"])
    @authorized(config)
    def handle_services_command(message):
        _show_services_menu(message)

    # Status
    @bot.message_handler(func=lambda m: m.text == _BTN_STATUS)
    @authorized(config)
    def handle_status(message):
        _get_status(message)

    # Start
    @bot.message_handler(func=lambda m: m.text == _BTN_START)
    @authorized(config)
    def handle_start_menu(message):
        markup = build_item_keyboard(config.services, "\u23ef Start service:", BTN_BACK_SERVICES)
        bot.send_message(message.chat.id, "Which service do you want to start?", reply_markup=markup)

    @bot.message_handler(func=lambda m: m.text and m.text.startswith("\u23ef Start service:"))
    @authorized(config)
    def handle_start_now(message):
        service = message.text.split(": ", 1)[1]
        _service_action(message, "start", service)

    # Restart
    @bot.message_handler(func=lambda m: m.text == _BTN_RESTART)
    @authorized(config)
    def handle_restart_menu(message):
        markup = build_item_keyboard(config.services, "\U0001f501 Restart service:", BTN_BACK_SERVICES)
        bot.send_message(message.chat.id, "Which service do you want to restart?", reply_markup=markup)

    @bot.message_handler(func=lambda m: m.text and m.text.startswith("\U0001f501 Restart service:"))
    @authorized(config)
    def handle_restart_now(message):
        service = message.text.split(": ", 1)[1]
        _service_action(message, "restart", service)

    # Stop
    @bot.message_handler(func=lambda m: m.text == _BTN_STOP)
    @authorized(config)
    def handle_stop_menu(message):
        markup = build_item_keyboard(config.services, "\u26d4 Stop service:", BTN_BACK_SERVICES)
        bot.send_message(message.chat.id, "Which service do you want to stop?", reply_markup=markup)

    @bot.message_handler(func=lambda m: m.text and m.text.startswith("\u26d4 Stop service:"))
    @authorized(config)
    def handle_stop_now(message):
        service = message.text.split(": ", 1)[1]
        _service_action(message, "stop", service)

    # All services
    @bot.message_handler(func=lambda m: m.text == _BTN_START_ALL)
    @authorized(config)
    def handle_start_all(message):
        _all_service_action(message, "start")

    @bot.message_handler(func=lambda m: m.text == _BTN_RESTART_ALL)
    @authorized(config)
    def handle_restart_all(message):
        _all_service_action(message, "restart")

    @bot.message_handler(func=lambda m: m.text == _BTN_STOP_ALL)
    @authorized(config)
    def handle_stop_all(message):
        _all_service_action(message, "stop")
