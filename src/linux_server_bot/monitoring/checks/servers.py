"""Server ping monitoring with state tracking."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from typing import TYPE_CHECKING

from linux_server_bot.shared.shell import run_command

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)


def _load_states(path: str) -> dict[str, str]:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_states(path: str, states: dict[str, str]) -> None:
    """Atomic write to prevent corruption."""
    dir_name = os.path.dirname(path) or "."
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(states, f)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _ping(host: str, port: int, timeout: int = 5) -> bool:
    result = run_command(["nc", "-zv", "-w", str(timeout), host, str(port)], timeout=timeout + 5)
    output = result.stdout + result.stderr
    return "succeeded" in output or "open" in output


def check_servers(bot: telebot.TeleBot, config: AppConfig) -> None:
    """Ping all monitored servers and send state-change notifications."""
    from linux_server_bot.shared.telegram import send_to_all

    states_path = config.server_states_path
    previous = _load_states(states_path)
    current: dict[str, str] = {}

    for server in config.monitoring.servers:
        name, host, port = server.name, server.host, server.port
        logger.info("Pinging %s at %s:%d", name, host, port)

        if _ping(host, port):
            current[name] = "online"
            if previous.get(name) in ("offline", "unknown"):
                send_to_all(bot, config, f"\u2705 Server {name} is back online.")
        else:
            # Retry with longer timeout
            time.sleep(5)
            if _ping(host, port, timeout=10):
                current[name] = "online"
                if previous.get(name) in ("offline", "unknown"):
                    send_to_all(bot, config, f"\u2705 Server {name} is back online.")
            else:
                current[name] = "offline"
                send_to_all(bot, config, f"\u26a0\ufe0f Server {name} is offline!")

    _save_states(states_path, current)
