"""Unified update handler -- system packages (apt) + container updates (script)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.callbacks import register_callback, safe_answer_callback_query
from linux_server_bot.bot.menus import (
    BTN_UPDATES,
    inline_action_keyboard,
    inline_confirm_keyboard,
)
from linux_server_bot.shared.actions.system_updates import (
    apply_system_updates,
    check_system_updates,
)
from linux_server_bot.shared.actions.updates import (
    dry_run_updates,
    rollback_updates,
    trigger_updates,
)
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.telegram import chunk_message, escape_html, send_loading

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_ACTIONS = [
    ("\U0001f50d System check", "sys_check"),
    ("\U0001f433 Container dry-run", "ctr_dryrun"),
    ("\U0001f4e6 Apply system", "sys_run"),
    ("✅ Apply containers", "ctr_run"),
    ("↩️ Rollback containers", "ctr_rollback"),
]


def _format_check_result(result: dict) -> str:
    count = result["count"]
    packages = result["packages"]
    rkhunter = result.get("rkhunter", False)

    if count == 0:
        return "✅ System is up to date. No packages to upgrade."

    lines = [f"\U0001f4e6 <b>{count} package(s) available for upgrade:</b>\n"]
    for pkg in packages:
        lines.append(f"  • {escape_html(pkg)}")

    lines.append("\n\U0001f4cb <b>This will run:</b>")
    lines.append("  <code>sudo apt-get upgrade -y</code>")
    if rkhunter:
        lines.append("  <code>sudo rkhunter --propupd</code>")

    return "\n".join(lines)


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register unified update handlers."""

    def _send_menu(chat_id: int) -> None:
        markup = inline_action_keyboard("updates", _ACTIONS, row_width=2)
        bot.send_message(chat_id, "Updates (system + containers):", reply_markup=markup)

    def _check_script() -> str | None:
        script = config.scripts.update_containers
        return script if script else None

    def _send_output(bot_inst, chat_id: int, loading_msg, text: str) -> None:
        chunks = chunk_message(text)
        if chunks:
            bot_inst.edit_message_text(chunks[0], chat_id, loading_msg.message_id)
            for chunk_text in chunks[1:]:
                bot_inst.send_message(chat_id, chunk_text)

    def _handle_callback(bot_inst, call, parts: list[str]) -> None:
        action = parts[0] if parts else None
        chat_id = call.message.chat.id

        if action == "cancel":
            safe_answer_callback_query(bot_inst, call.id, "Cancelled")
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return

        # -- System check (apt list --upgradable) ----------------------------
        if action == "sys_check":
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            loading = send_loading(bot_inst, chat_id, "Checking for system updates")
            result = check_system_updates()

            if not result["success"]:
                _send_output(bot_inst, chat_id, loading, escape_html(result.get("output", "Failed to check.")))
                return

            text = _format_check_result(result)
            bot_inst.edit_message_text(text, chat_id, loading.message_id, parse_mode="HTML")

            if result["count"] > 0:
                markup = inline_confirm_keyboard("updates", "sys_confirm")
                bot_inst.send_message(chat_id, f"Apply {result['count']} update(s)?", reply_markup=markup)
            return

        # -- System apply (apt-get upgrade -y) --------------------------------
        if action == "sys_run":
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            loading = send_loading(bot_inst, chat_id, "Checking for system updates")
            result = check_system_updates()

            if not result["success"]:
                _send_output(bot_inst, chat_id, loading, escape_html(result.get("output", "Failed to check.")))
                return

            text = _format_check_result(result)
            bot_inst.edit_message_text(text, chat_id, loading.message_id, parse_mode="HTML")

            if result["count"] == 0:
                return

            markup = inline_confirm_keyboard("updates", "sys_confirm")
            bot_inst.send_message(chat_id, f"Apply {result['count']} update(s)?", reply_markup=markup)
            return

        # -- System confirm/cancel --------------------------------------------
        if action == "sys_confirm":
            confirm = parts[1] if len(parts) > 1 else None
            if confirm == "cancel":
                safe_answer_callback_query(bot_inst, call.id, "Cancelled")
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                return
            if confirm == "confirm":
                safe_answer_callback_query(bot_inst, call.id)
                bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                loading = send_loading(bot_inst, chat_id, "Installing system updates")
                result = apply_system_updates()
                _send_output(bot_inst, chat_id, loading, escape_html(result.get("output", "No output.")))
                icon = "✅" if result["success"] else "⚠️"
                label = "System updates completed." if result["success"] else "System updates finished with errors."
                bot_inst.send_message(chat_id, f"{icon} {label}")
                return
            return

        # -- Container dry-run ------------------------------------------------
        if action == "ctr_dryrun":
            script = _check_script()
            if not script:
                safe_answer_callback_query(bot_inst, call.id, "Script not configured")
                bot_inst.send_message(
                    chat_id,
                    "Update script not configured in config.yaml (scripts.update_containers).",
                )
                return
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            loading = send_loading(bot_inst, chat_id, "Container dry-run")
            result = dry_run_updates(script)
            _send_output(bot_inst, chat_id, loading, escape_html(result.get("output", "No output.")))
            return

        # -- Container run ----------------------------------------------------
        if action == "ctr_run":
            script = _check_script()
            if not script:
                safe_answer_callback_query(bot_inst, call.id, "Script not configured")
                bot_inst.send_message(
                    chat_id,
                    "Update script not configured in config.yaml (scripts.update_containers).",
                )
                return
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            loading = send_loading(bot_inst, chat_id, "Applying container updates")
            result = trigger_updates(script)
            _send_output(bot_inst, chat_id, loading, escape_html(result.get("output", "No output.")))
            icon = "✅" if result["success"] else "⚠️"
            label = "Container updates completed." if result["success"] else "Container updates finished with errors."
            bot_inst.send_message(chat_id, f"{icon} {label}")
            return

        # -- Container rollback -----------------------------------------------
        if action == "ctr_rollback":
            script = _check_script()
            if not script:
                safe_answer_callback_query(bot_inst, call.id, "Script not configured")
                bot_inst.send_message(
                    chat_id,
                    "Update script not configured in config.yaml (scripts.update_containers).",
                )
                return
            safe_answer_callback_query(bot_inst, call.id)
            bot_inst.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            loading = send_loading(bot_inst, chat_id, "Rolling back containers")
            result = rollback_updates(script)
            _send_output(bot_inst, chat_id, loading, escape_html(result.get("output", "No output.")))
            return

        safe_answer_callback_query(bot_inst, call.id, "Unknown action")

    register_callback("updates", _handle_callback)

    @bot.message_handler(func=lambda m: m.text == BTN_UPDATES)
    @authorized(config)
    def handle_updates_menu(message):
        _send_menu(message.chat.id)

    @bot.message_handler(commands=["updates"])
    @authorized(config)
    def handle_updates_command(message):
        _send_menu(message.chat.id)
