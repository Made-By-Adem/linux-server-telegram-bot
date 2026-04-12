"""Docker container management handlers."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from linux_server_bot.bot.menus import (
    BTN_BACK_DOCKER,
    BTN_BACK_MAIN,
    BTN_DOCKER,
    build_action_keyboard,
    build_item_keyboard,
)
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.shell import run_command

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_BTN_START = "\U0001f7e9 Start a docker container"
_BTN_RESTART = "\U0001f7e8 Restart a docker container"
_BTN_STOP = "\U0001f7e5 Stop a docker container"
_BTN_START_ALL = "\U0001f7e9\U0001f7e9 Start all docker containers"
_BTN_RESTART_ALL = "\U0001f7e8\U0001f7e8 Restart all docker containers"
_BTN_STOP_ALL = "\U0001f7e5\U0001f7e5 Stop all docker containers"
_BTN_STATUS = "\U0001f7eb Get status containers"


def _get_container_names() -> list[str]:
    """Dynamically fetch all container names from Docker."""
    result = run_command(["docker", "ps", "-a", "--format", "{{.Names}}"])
    if result.success and result.stdout.strip():
        return [n for n in result.stdout.strip().split("\n") if n]
    return []


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register all Docker container management handlers."""

    def _show_docker_menu(message):
        actions = [_BTN_START, _BTN_RESTART, _BTN_STOP,
                   _BTN_START_ALL, _BTN_RESTART_ALL, _BTN_STOP_ALL, _BTN_STATUS]
        markup = build_action_keyboard(actions, back_button=BTN_BACK_MAIN, row_width=3)
        bot.send_message(message.chat.id, "What do you want to do?", reply_markup=markup)

    def _get_status(message):
        logger.info("User %s requested container status", message.from_user.first_name)
        result = run_command([
            "docker", "ps", "-a",
            "--format", "Name: {{.Names}}\nCreated at: {{.CreatedAt}}\nStatus: {{.Status}}\n",
        ])
        status_msg = "<b>Status containers:</b>\n" + (result.stdout if result.success else f"Error: {result.stderr}")
        bot.send_message(message.chat.id, status_msg, parse_mode="HTML")
        _show_docker_menu(message)

    def _container_action(message, action: str, container: str):
        logger.info("User %s requested docker %s: %s", message.from_user.first_name, action, container)
        bot.reply_to(message, f"{action.capitalize()}ing {container}...")
        result = run_command(["sudo", "docker", action, container])
        if not result.success:
            bot.reply_to(message, f"{action.capitalize()}ing {container} failed: {result.stderr}")
        _get_status(message)

    def _all_container_action(message, action: str):
        logger.info("User %s requested docker %s all", message.from_user.first_name, action)
        containers = _get_container_names()
        for container in containers:
            bot.reply_to(message, f"{action.capitalize()}ing {container}...")
            result = run_command(["sudo", "docker", action, container])
            if not result.success:
                bot.reply_to(message, f"{action.capitalize()}ing {container} failed: {result.stderr}")
        time.sleep(1)
        _get_status(message)

    # Docker menu
    @bot.message_handler(func=lambda m: m.text == BTN_DOCKER)
    @authorized(config)
    def handle_docker_menu(message):
        _show_docker_menu(message)

    @bot.message_handler(func=lambda m: m.text and m.text.startswith(BTN_BACK_DOCKER))
    @authorized(config)
    def handle_docker_back(message):
        _show_docker_menu(message)

    @bot.message_handler(commands=["docker"])
    @authorized(config)
    def handle_docker_command(message):
        _show_docker_menu(message)

    # Status
    @bot.message_handler(func=lambda m: m.text == _BTN_STATUS)
    @authorized(config)
    def handle_status(message):
        _get_status(message)

    # Start
    @bot.message_handler(func=lambda m: m.text == _BTN_START)
    @authorized(config)
    def handle_start_menu(message):
        containers = _get_container_names()
        markup = build_item_keyboard(containers, "\u23ef Start container:", BTN_BACK_DOCKER)
        bot.send_message(message.chat.id, "Which container do you want to start?", reply_markup=markup)

    @bot.message_handler(func=lambda m: m.text and m.text.startswith("\u23ef Start container:"))
    @authorized(config)
    def handle_start_now(message):
        container = message.text.split(": ", 1)[1]
        _container_action(message, "start", container)

    # Restart
    @bot.message_handler(func=lambda m: m.text == _BTN_RESTART)
    @authorized(config)
    def handle_restart_menu(message):
        containers = _get_container_names()
        markup = build_item_keyboard(containers, "\U0001f501 Restart container:", BTN_BACK_DOCKER)
        bot.send_message(message.chat.id, "Which container do you want to restart?", reply_markup=markup)

    @bot.message_handler(func=lambda m: m.text and m.text.startswith("\U0001f501 Restart container:"))
    @authorized(config)
    def handle_restart_now(message):
        container = message.text.split(": ", 1)[1]
        _container_action(message, "restart", container)

    # Stop
    @bot.message_handler(func=lambda m: m.text == _BTN_STOP)
    @authorized(config)
    def handle_stop_menu(message):
        containers = _get_container_names()
        markup = build_item_keyboard(containers, "\u26d4 Stop container:", BTN_BACK_DOCKER)
        bot.send_message(message.chat.id, "Which container do you want to stop?", reply_markup=markup)

    @bot.message_handler(func=lambda m: m.text and m.text.startswith("\u26d4 Stop container:"))
    @authorized(config)
    def handle_stop_now(message):
        container = message.text.split(": ", 1)[1]
        _container_action(message, "stop", container)

    # All containers
    @bot.message_handler(func=lambda m: m.text == _BTN_START_ALL)
    @authorized(config)
    def handle_start_all(message):
        _all_container_action(message, "start")

    @bot.message_handler(func=lambda m: m.text == _BTN_RESTART_ALL)
    @authorized(config)
    def handle_restart_all(message):
        _all_container_action(message, "restart")

    @bot.message_handler(func=lambda m: m.text == _BTN_STOP_ALL)
    @authorized(config)
    def handle_stop_all(message):
        _all_container_action(message, "stop")
