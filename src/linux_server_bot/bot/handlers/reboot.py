"""Server reboot and bot restart handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback, safe_answer_callback_query
from linux_server_bot.bot.menus import BTN_REBOOT, inline_action_keyboard, inline_confirm_keyboard
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.shell import run_command

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

# The compose services that make up this application.
_BOT_SERVICES = ["bot", "monitoring", "api"]

_ACTIONS = [
    ("\U0001f501 Reboot server", "reboot"),
    ("\U0001f504 Restart bot", "restart_bot"),
]


def _restart_compose_service(service: str, timeout: int = 60) -> dict:
    """Restart a single compose service by finding its container via labels."""
    result = run_command(
        ["docker", "ps", "-qf", f"label=com.docker.compose.service={service}"],
        timeout=10,
    )
    container_id = result.stdout.strip()
    if not container_id:
        return {"success": False, "error": f"Container for service '{service}' not found"}
    result = run_command(["docker", "restart", container_id], timeout=timeout)
    if result.success:
        return {"success": True}
    return {"success": False, "error": result.stderr.strip() or "Unknown error"}


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register reboot and bot restart handlers."""

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        chat_id = call.message.chat.id

        if action == "cancel":
            safe_answer_callback_query(bot_inst, call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        # --- Server reboot ---
        if action == "reboot" and len(parts) > 1:
            if parts[1] == "confirm":
                safe_answer_callback_query(bot_inst, call.id, "Rebooting...")
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                logger.info("User confirmed server reboot")
                bot_inst.send_message(chat_id, "\U0001f501 Rebooting the server...")
                run_command(["sudo", "reboot", "now"])
                return
            if parts[1] == "cancel":
                safe_answer_callback_query(bot_inst, call.id, "Cancelled")
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                return

        if action == "reboot" and len(parts) == 1:
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            markup = inline_confirm_keyboard("reboot", "reboot")
            bot_inst.send_message(chat_id, "Are you sure you want to reboot the server?", reply_markup=markup)
            return

        # --- Restart bot (all bot containers) ---
        if action == "restart_bot" and len(parts) > 1:
            if parts[1] == "confirm":
                safe_answer_callback_query(bot_inst, call.id, "Restarting...")
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                logger.info("User confirmed bot restart")
                bot_inst.send_message(
                    chat_id,
                    "\U0001f504 Restarting bot containers... I'll be back in a moment.",
                )
                # Restart monitoring and api first, bot last so the message is sent
                for svc in _BOT_SERVICES:
                    if svc == "bot":
                        continue
                    result = _restart_compose_service(svc)
                    if not result["success"]:
                        logger.warning("Failed to restart %s: %s", svc, result["error"])
                _restart_compose_service("bot")
                return
            if parts[1] == "cancel":
                safe_answer_callback_query(bot_inst, call.id, "Cancelled")
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                return

        if action == "restart_bot" and len(parts) == 1:
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            markup = inline_confirm_keyboard("reboot", "restart_bot")
            bot_inst.send_message(
                chat_id,
                "Restart all bot containers (bot, monitoring, API)?",
                reply_markup=markup,
            )
            return

        safe_answer_callback_query(bot_inst, call.id, "Unknown action")

    register_callback("reboot", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_REBOOT)
    @authorized(config)
    def handle_reboot_menu(message):
        markup = inline_action_keyboard("reboot", _ACTIONS, row_width=1)
        bot.send_message(message.chat.id, "Choose an action:", reply_markup=markup)

    @bot.message_handler(commands=["reboot"])
    @authorized(config)
    def handle_reboot_command(message):
        handle_reboot_menu(message)
