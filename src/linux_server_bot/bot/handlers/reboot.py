"""Server reboot and container restart handler."""

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

# The three compose services that make up this application.
_COMPOSE_SERVICES = ["bot", "monitoring", "api"]

_ACTIONS = [
    ("\U0001f501 Reboot server", "reboot"),
    ("\U0001f504 Restart all containers", "restart_all"),
    ("\U0001f916 Restart bot", "restart_svc:bot"),
    ("\U0001f4ca Restart monitoring", "restart_svc:monitoring"),
    ("\U0001f310 Restart API", "restart_svc:api"),
]


def _restart_compose_service(service: str, timeout: int = 60) -> dict:
    """Restart a single compose service by finding its container via labels."""
    # Find the container ID by compose service label
    result = run_command(
        ["docker", "ps", "-qf", f"label=com.docker.compose.service={service}"],
        timeout=10,
    )
    container_id = result.stdout.strip()
    if not container_id:
        return {"success": False, "error": f"Container for service '{service}' not found"}
    # Restart by container ID
    result = run_command(["docker", "restart", container_id], timeout=timeout)
    if result.success:
        return {"success": True}
    return {"success": False, "error": result.stderr.strip() or "Unknown error"}


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register reboot and container restart handlers."""

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

        # --- Restart all containers ---
        if action == "restart_all" and len(parts) > 1:
            if parts[1] == "confirm":
                safe_answer_callback_query(bot_inst, call.id, "Restarting...")
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                logger.info("User confirmed restart of all containers")
                bot_inst.send_message(
                    chat_id,
                    "\U0001f504 Restarting all containers (bot, monitoring, API)... I'll be back in a moment.",
                )
                for svc in _COMPOSE_SERVICES:
                    if svc == "bot":
                        continue  # restart bot last so the message is sent
                    _restart_compose_service(svc)
                _restart_compose_service("bot")
                return
            if parts[1] == "cancel":
                safe_answer_callback_query(bot_inst, call.id, "Cancelled")
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                return

        if action == "restart_all" and len(parts) == 1:
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            markup = inline_confirm_keyboard("reboot", "restart_all")
            bot_inst.send_message(
                chat_id,
                "Restart all containers (bot, monitoring, API)?",
                reply_markup=markup,
            )
            return

        # --- Restart individual container ---
        if action == "restart_svc":
            service = parts[1] if len(parts) > 1 else None
            confirm = parts[2] if len(parts) > 2 else None

            if not service or service not in _COMPOSE_SERVICES:
                safe_answer_callback_query(bot_inst, call.id, "Unknown service")
                return

            if confirm == "confirm":
                safe_answer_callback_query(bot_inst, call.id, f"Restarting {service}...")
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                logger.info("User confirmed restart of %s", service)
                bot_inst.send_message(chat_id, f"\U0001f504 Restarting <b>{service}</b>...", parse_mode="HTML")
                result = _restart_compose_service(service)
                if result["success"]:
                    if service != "bot":
                        bot_inst.send_message(chat_id, f"\u2705 <b>{service}</b> restarted.", parse_mode="HTML")
                else:
                    bot_inst.send_message(
                        chat_id,
                        f"\u26a0\ufe0f Failed to restart <b>{service}</b>: {result['error']}",
                        parse_mode="HTML",
                    )
                return
            if confirm == "cancel":
                safe_answer_callback_query(bot_inst, call.id, "Cancelled")
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                return

            # Show confirmation
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            markup = inline_confirm_keyboard("reboot", f"restart_svc:{service}")
            bot_inst.send_message(
                chat_id,
                f"Restart the <b>{service}</b> container?",
                reply_markup=markup,
                parse_mode="HTML",
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
