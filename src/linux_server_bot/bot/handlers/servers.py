"""Server ping/health check handlers."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from typing import TYPE_CHECKING

from linux_server_bot.bot.menus import BTN_BACK_MAIN, BTN_SERVERS, build_item_keyboard
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.shell import run_command

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)


def _load_server_states(path: str) -> dict[str, str]:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_server_states(path: str, states: dict[str, str]) -> None:
    """Atomic write to avoid corruption from concurrent access."""
    dir_name = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(states, f)
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)
        raise


def _ping_server(host: str, port: int, timeout: int = 5) -> bool:
    """Ping a server using netcat. Returns True if reachable."""
    result = run_command(["nc", "-zv", "-w", str(timeout), host, str(port)], timeout=timeout + 5)
    output = result.stdout + result.stderr
    return "succeeded" in output or "open" in output


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register server ping handlers."""

    def _show_servers_menu(message):
        server_names = [s.name for s in config.servers]
        markup = build_item_keyboard(server_names, "\U0001f514 Ping:", BTN_BACK_MAIN)
        bot.send_message(message.chat.id, "Which server do you want to ping?", reply_markup=markup)

    def _do_ping(message, name: str, host: str, port: int):
        logger.info("Pinging %s at %s:%d", name, host, port)
        states = _load_server_states(config.server_states_path)

        if _ping_server(host, port):
            prev = states.get(name)
            if prev in ("offline", "unknown"):
                bot.send_message(message.chat.id, f"\u2705 Server {name} is back online.")
            else:
                bot.send_message(message.chat.id, f"\u2705 Server {name} is online.")
            states[name] = "online"
        else:
            # Retry once after 5 seconds with longer timeout
            time.sleep(5)
            if _ping_server(host, port, timeout=10):
                prev = states.get(name)
                if prev in ("offline", "unknown"):
                    bot.send_message(message.chat.id, f"\u2705 Server {name} is back online.")
                else:
                    bot.send_message(message.chat.id, f"\u2705 Server {name} is online.")
                states[name] = "online"
            else:
                bot.send_message(message.chat.id, f"\u26a0\ufe0f Server {name} is offline!")
                states[name] = "offline"

        _save_server_states(config.server_states_path, states)

    @bot.message_handler(func=lambda m: m.text == BTN_SERVERS)
    @authorized(config)
    def handle_servers_menu(message):
        _show_servers_menu(message)

    @bot.message_handler(commands=["ping"])
    @authorized(config)
    def handle_ping_command(message):
        _show_servers_menu(message)

    @bot.message_handler(func=lambda m: m.text and m.text.startswith("\U0001f514 Ping:"))
    @authorized(config)
    def handle_ping_server(message):
        server_name = message.text.split(": ", 1)[1] if ": " in message.text else message.text.split(" ", 2)[-1]
        for server in config.servers:
            if server.name == server_name:
                _do_ping(message, server.name, server.host, server.port)
                break
        else:
            bot.send_message(message.chat.id, f"Server '{server_name}' not found in config.")
        _show_servers_menu(message)
