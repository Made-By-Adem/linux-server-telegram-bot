"""Server ping/health check handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback
from linux_server_bot.bot.menus import BTN_SERVERS, inline_item_keyboard
from linux_server_bot.shared.actions.servers import (
    load_server_states,
    ping_server_with_retry,
    save_server_states,
)
from linux_server_bot.shared.auth import authorized

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register server ping handlers."""

    def _send_servers_menu(chat_id: int) -> None:
        server_names = [s.name for s in config.servers]
        if not server_names:
            bot.send_message(chat_id, "No servers configured.")
            return
        markup = inline_item_keyboard("servers", "ping", server_names, row_width=2)
        bot.send_message(chat_id, "Which server do you want to ping?", reply_markup=markup)

    def _do_ping(chat_id: int, name: str, host: str, port: int) -> None:
        logger.info("Pinging %s at %s:%d", name, host, port)
        states = load_server_states(config.server_states_path)

        result = ping_server_with_retry(name, host, port)
        prev = states.get(name)

        if result["status"] == "online":
            if prev in ("offline", "unknown"):
                bot.send_message(chat_id, f"\u2705 Server {name} is back online.")
            else:
                bot.send_message(chat_id, f"\u2705 Server {name} is online.")
            states[name] = "online"
        else:
            bot.send_message(chat_id, f"\u26a0\ufe0f Server {name} is offline!")
            states[name] = "offline"

        save_server_states(config.server_states_path, states)

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        target = parts[1] if len(parts) > 1 else None
        chat_id = call.message.chat.id

        if action == "cancel":
            bot_inst.answer_callback_query(call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        if action == "ping" and target:
            for server in config.servers:
                if server.name == target:
                    bot_inst.answer_callback_query(call.id, f"Pinging {target}...")
                    _do_ping(chat_id, server.name, server.host, server.port)
                    return
            bot_inst.answer_callback_query(call.id, f"Server '{target}' not found")
            return

        bot_inst.answer_callback_query(call.id, "Unknown action")

    register_callback("servers", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_SERVERS)
    @authorized(config)
    def handle_servers_menu(message):
        _send_servers_menu(message.chat.id)
        show_menu(message)

    @bot.message_handler(commands=["ping"])
    @authorized(config)
    def handle_ping_command(message):
        _send_servers_menu(message.chat.id)
        show_menu(message)
