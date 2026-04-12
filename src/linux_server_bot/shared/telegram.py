"""Shared Telegram bot instance and messaging helpers."""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING

import telebot

if TYPE_CHECKING:
    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_MAX_MESSAGE_LENGTH = 4000  # Telegram limit is 4096, leave margin


def create_bot(token: str) -> telebot.TeleBot:
    """Create a TeleBot instance with HTML parse mode."""
    return telebot.TeleBot(token, parse_mode="HTML")


def chunk_message(text: str, max_length: int = _MAX_MESSAGE_LENGTH) -> list[str]:
    """Split text into chunks that fit within Telegram's message limit.

    Tries to split at newline boundaries for readability.
    """
    if len(text) <= max_length:
        return [text] if text.strip() else []

    chunks: list[str] = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        # Try to split at last newline within limit
        split_pos = text.rfind("\n", 0, max_length)
        if split_pos <= 0:
            # No newline found, split at max_length
            split_pos = max_length

        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip("\n")

    return chunks


def escape_html(text: str) -> str:
    """Escape text for safe use in Telegram HTML messages."""
    return html.escape(text)


def send_message(bot: telebot.TeleBot, chat_id: int, text: str, parse_mode: str | None = "HTML") -> None:
    """Send a message, automatically chunking if too long."""
    chunks = chunk_message(text)
    if not chunks:
        bot.send_message(chat_id, "The command output is empty.")
        return
    for chunk in chunks:
        try:
            bot.send_message(chat_id, chunk, parse_mode=parse_mode)
        except Exception:
            logger.exception("Failed to send message to chat_id=%s", chat_id)


def send_to_all(bot: telebot.TeleBot, config: AppConfig, text: str, parse_mode: str | None = None) -> None:
    """Send a notification message to all allowed users."""
    for chat_id in config.allowed_users:
        try:
            bot.send_message(chat_id, text, parse_mode=parse_mode)
        except Exception:
            logger.exception("Failed to send notification to chat_id=%s", chat_id)
