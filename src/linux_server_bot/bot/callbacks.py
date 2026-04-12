"""Central callback query router for InlineKeyboard interactions.

Each handler module registers its callback handler via ``register_callback()``.
The router parses ``callback_data`` (format: ``module:action[:target[:extra]]``)
and dispatches to the appropriate module handler.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

# module_name -> handler(bot, call, parts)
# where *parts* is the list of callback_data segments AFTER the module name.
_handlers: dict[str, Callable] = {}


def register_callback(module: str, handler: Callable) -> None:
    """Register a module's callback handler.

    Parameters
    ----------
    module:
        Key that matches the first segment of ``callback_data``,
        e.g. ``"docker"`` matches ``"docker:start:nginx"``.
    handler:
        ``handler(bot, call, parts)`` where *parts* is
        ``["start", "nginx"]`` for ``"docker:start:nginx"``.
    """
    _handlers[module] = handler


def setup_callback_router(bot: telebot.TeleBot, config: AppConfig) -> None:
    """Register the central ``callback_query_handler`` on the bot.

    Must be called **after** all handler modules have registered their
    callbacks via ``register_callback()``.
    """

    @bot.callback_query_handler(func=lambda call: True)
    def route_callback(call):
        if not call.data:
            bot.answer_callback_query(call.id)
            return

        parts = call.data.split(":")
        module = parts[0]

        # Auth check
        if call.message.chat.id not in config.allowed_users:
            bot.answer_callback_query(call.id, "Unauthorized")
            return

        handler = _handlers.get(module)
        if handler:
            try:
                handler(bot, call, parts[1:])
            except Exception:
                logger.exception("Callback handler error for %s", call.data)
                bot.answer_callback_query(call.id, "An error occurred")
        else:
            bot.answer_callback_query(call.id, "Unknown action")
