"""Docker Compose stack management handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.menus import (
    BTN_BACK_COMPOSE,
    BTN_BACK_MAIN,
    BTN_COMPOSE,
    build_action_keyboard,
    build_item_keyboard,
)
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.shell import run_command
from linux_server_bot.shared.telegram import chunk_message, escape_html

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_BTN_STATUS = "\U0001f6a2 Stack status"
_BTN_UP = "\U0001f7e9 Stack up"
_BTN_DOWN = "\U0001f7e5 Stack down"
_BTN_RESTART = "\U0001f7e8 Stack restart"
_BTN_PULL = "\U0001f504 Stack pull & recreate"
_BTN_LOGS = "\U0001f4dc Stack logs"


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register Docker Compose stack management handlers."""

    def _stack_names() -> list[str]:
        return [s.name for s in config.compose_stacks]

    def _stack_path(name: str) -> str | None:
        for s in config.compose_stacks:
            if s.name == name:
                return s.path
        return None

    def _show_compose_menu(message):
        actions = [_BTN_STATUS, _BTN_UP, _BTN_DOWN, _BTN_RESTART, _BTN_PULL, _BTN_LOGS]
        markup = build_action_keyboard(actions, back_button=BTN_BACK_MAIN, row_width=3)
        bot.send_message(message.chat.id, "Docker Compose stack management:", reply_markup=markup)

    def _run_compose(path: str, args: list[str], timeout: int = 120):
        return run_command(["docker", "compose", "-f", f"{path}/docker-compose.yml"] + args, timeout=timeout)

    @bot.message_handler(func=lambda m: m.text == BTN_COMPOSE)
    @authorized(config)
    def handle_compose_menu(message):
        _show_compose_menu(message)

    @bot.message_handler(func=lambda m: m.text and m.text.startswith(BTN_BACK_COMPOSE))
    @authorized(config)
    def handle_compose_back(message):
        _show_compose_menu(message)

    # Status
    @bot.message_handler(func=lambda m: m.text == _BTN_STATUS)
    @authorized(config)
    def handle_status(message):
        logger.info("User %s requested compose status", message.from_user.first_name)
        for stack in config.compose_stacks:
            result = _run_compose(stack.path, ["ps", "--format", "table {{.Name}}\t{{.Status}}"])
            header = f"<b>{stack.name}</b> ({stack.path}):\n"
            output = result.stdout.strip() if result.success else f"Error: {result.stderr}"
            bot.send_message(message.chat.id, header + escape_html(output))
        _show_compose_menu(message)

    # Up
    @bot.message_handler(func=lambda m: m.text == _BTN_UP)
    @authorized(config)
    def handle_up_menu(message):
        markup = build_item_keyboard(_stack_names(), "\U0001f7e9 Up stack:", BTN_BACK_COMPOSE)
        bot.send_message(message.chat.id, "Which stack to bring up?", reply_markup=markup)

    @bot.message_handler(func=lambda m: m.text and m.text.startswith("\U0001f7e9 Up stack:"))
    @authorized(config)
    def handle_up_now(message):
        name = message.text.split(": ", 1)[1]
        path = _stack_path(name)
        if not path:
            bot.send_message(message.chat.id, f"Stack '{name}' not found.")
            _show_compose_menu(message)
            return
        logger.info("User %s bringing up stack %s", message.from_user.first_name, name)
        bot.reply_to(message, f"Bringing up {name}...")
        result = _run_compose(path, ["up", "-d"])
        if result.success:
            bot.send_message(message.chat.id, f"\u2705 Stack {name} is up.")
        else:
            bot.send_message(message.chat.id, f"\u26a0\ufe0f Failed: {result.stderr[:500]}")
        _show_compose_menu(message)

    # Down
    @bot.message_handler(func=lambda m: m.text == _BTN_DOWN)
    @authorized(config)
    def handle_down_menu(message):
        markup = build_item_keyboard(_stack_names(), "\U0001f7e5 Down stack:", BTN_BACK_COMPOSE)
        bot.send_message(message.chat.id, "Which stack to bring down?", reply_markup=markup)

    @bot.message_handler(func=lambda m: m.text and m.text.startswith("\U0001f7e5 Down stack:"))
    @authorized(config)
    def handle_down_now(message):
        name = message.text.split(": ", 1)[1]
        path = _stack_path(name)
        if not path:
            bot.send_message(message.chat.id, f"Stack '{name}' not found.")
            _show_compose_menu(message)
            return
        logger.info("User %s bringing down stack %s", message.from_user.first_name, name)
        bot.reply_to(message, f"Bringing down {name}...")
        result = _run_compose(path, ["down"])
        if result.success:
            bot.send_message(message.chat.id, f"\u2705 Stack {name} is down.")
        else:
            bot.send_message(message.chat.id, f"\u26a0\ufe0f Failed: {result.stderr[:500]}")
        _show_compose_menu(message)

    # Restart
    @bot.message_handler(func=lambda m: m.text == _BTN_RESTART)
    @authorized(config)
    def handle_restart_menu(message):
        markup = build_item_keyboard(_stack_names(), "\U0001f7e8 Restart stack:", BTN_BACK_COMPOSE)
        bot.send_message(message.chat.id, "Which stack to restart?", reply_markup=markup)

    @bot.message_handler(func=lambda m: m.text and m.text.startswith("\U0001f7e8 Restart stack:"))
    @authorized(config)
    def handle_restart_now(message):
        name = message.text.split(": ", 1)[1]
        path = _stack_path(name)
        if not path:
            bot.send_message(message.chat.id, f"Stack '{name}' not found.")
            _show_compose_menu(message)
            return
        logger.info("User %s restarting stack %s", message.from_user.first_name, name)
        bot.reply_to(message, f"Restarting {name}...")
        result = _run_compose(path, ["restart"])
        if result.success:
            bot.send_message(message.chat.id, f"\u2705 Stack {name} restarted.")
        else:
            bot.send_message(message.chat.id, f"\u26a0\ufe0f Failed: {result.stderr[:500]}")
        _show_compose_menu(message)

    # Pull & recreate
    @bot.message_handler(func=lambda m: m.text == _BTN_PULL)
    @authorized(config)
    def handle_pull_menu(message):
        markup = build_item_keyboard(_stack_names(), "\U0001f504 Pull stack:", BTN_BACK_COMPOSE)
        bot.send_message(message.chat.id, "Which stack to pull & recreate?", reply_markup=markup)

    @bot.message_handler(func=lambda m: m.text and m.text.startswith("\U0001f504 Pull stack:"))
    @authorized(config)
    def handle_pull_now(message):
        name = message.text.split(": ", 1)[1]
        path = _stack_path(name)
        if not path:
            bot.send_message(message.chat.id, f"Stack '{name}' not found.")
            _show_compose_menu(message)
            return
        logger.info("User %s pulling stack %s", message.from_user.first_name, name)
        bot.reply_to(message, f"Pulling images for {name}...")
        pull_result = _run_compose(path, ["pull"], timeout=300)
        if not pull_result.success:
            bot.send_message(message.chat.id, f"\u26a0\ufe0f Pull failed: {pull_result.stderr[:500]}")
            _show_compose_menu(message)
            return
        bot.send_message(message.chat.id, "Recreating containers...")
        up_result = _run_compose(path, ["up", "-d", "--force-recreate"])
        if up_result.success:
            bot.send_message(message.chat.id, f"\u2705 Stack {name} updated and recreated.")
        else:
            bot.send_message(message.chat.id, f"\u26a0\ufe0f Recreate failed: {up_result.stderr[:500]}")
        _show_compose_menu(message)

    # Logs
    @bot.message_handler(func=lambda m: m.text == _BTN_LOGS)
    @authorized(config)
    def handle_logs_menu(message):
        markup = build_item_keyboard(_stack_names(), "\U0001f4dc Logs stack:", BTN_BACK_COMPOSE)
        bot.send_message(message.chat.id, "Which stack logs to view?", reply_markup=markup)

    @bot.message_handler(func=lambda m: m.text and m.text.startswith("\U0001f4dc Logs stack:"))
    @authorized(config)
    def handle_logs_now(message):
        name = message.text.split(": ", 1)[1]
        path = _stack_path(name)
        if not path:
            bot.send_message(message.chat.id, f"Stack '{name}' not found.")
            _show_compose_menu(message)
            return
        logger.info("User %s viewing logs for stack %s", message.from_user.first_name, name)
        result = _run_compose(path, ["logs", "--tail", "50"])
        output = result.stdout or result.stderr
        if output.strip():
            for chunk in chunk_message(escape_html(output)):
                bot.send_message(message.chat.id, chunk)
        else:
            bot.send_message(message.chat.id, "No logs available.")
        _show_compose_menu(message)
