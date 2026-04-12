"""Authorization decorator for Telegram bot handlers."""

from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)


def authorized(config: AppConfig):
    """Decorator factory that restricts a handler to allowed users.

    Usage::

        @bot.message_handler(...)
        @authorized(config)
        def my_handler(message):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(message, *args, **kwargs):
            if message.chat.id not in config.allowed_users:
                logger.warning(
                    "Unauthorized access attempt from chat_id=%s user=%s",
                    message.chat.id,
                    getattr(message.from_user, "first_name", "unknown"),
                )
                return
            return func(message, *args, **kwargs)
        return wrapper
    return decorator
