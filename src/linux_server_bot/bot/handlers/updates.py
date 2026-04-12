"""Container update trigger handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from linux_server_bot.bot.menus import BTN_BACK_MAIN, BTN_UPDATES, build_action_keyboard
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.shell import run_shell
from linux_server_bot.shared.telegram import chunk_message, escape_html

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

logger = logging.getLogger(__name__)

_BTN_DRY_RUN = "\U0001f50d Dry run updates"
_BTN_RUN = "\u2705 Run updates"
_BTN_ROLLBACK = "\u21a9\ufe0f Rollback"


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register container update trigger handlers."""

    def _show_updates_menu(message):
        actions = [_BTN_DRY_RUN, _BTN_RUN, _BTN_ROLLBACK]
        markup = build_action_keyboard(actions, BTN_BACK_MAIN, row_width=3)
        bot.send_message(message.chat.id, "Container updates:", reply_markup=markup)

    def _check_script():
        script = config.scripts.update_containers
        if not script:
            return None
        return script

    @bot.message_handler(func=lambda m: m.text == BTN_UPDATES)
    @authorized(config)
    def handle_updates_menu(message):
        _show_updates_menu(message)

    @bot.message_handler(func=lambda m: m.text == _BTN_DRY_RUN)
    @authorized(config)
    def handle_dry_run(message):
        script = _check_script()
        if not script:
            bot.send_message(
                message.chat.id, "Update script not configured in config.yaml (scripts.update_containers).",
            )
            _show_updates_menu(message)
            return
        logger.info("User %s triggered update dry-run", message.from_user.first_name)
        bot.reply_to(message, "Running dry-run...")
        result = run_shell(f"sudo {script} --dry-run 2>&1", timeout=300)
        output = result.stdout or result.stderr or "No output."
        for chunk_text in chunk_message(escape_html(output)):
            bot.send_message(message.chat.id, chunk_text)
        _show_updates_menu(message)

    @bot.message_handler(func=lambda m: m.text == _BTN_RUN)
    @authorized(config)
    def handle_run_updates(message):
        script = _check_script()
        if not script:
            bot.send_message(message.chat.id, "Update script not configured.")
            _show_updates_menu(message)
            return
        logger.info("User %s triggered container updates", message.from_user.first_name)
        bot.reply_to(message, "Starting container updates (this may take a while)...")
        result = run_shell(f"sudo {script} 2>&1", timeout=600)
        output = result.stdout or result.stderr or "No output."
        for chunk_text in chunk_message(escape_html(output)):
            bot.send_message(message.chat.id, chunk_text)
        if result.success:
            bot.send_message(message.chat.id, "\u2705 Container updates completed.")
        else:
            bot.send_message(message.chat.id, "\u26a0\ufe0f Updates finished with errors.")
        _show_updates_menu(message)

    @bot.message_handler(func=lambda m: m.text == _BTN_ROLLBACK)
    @authorized(config)
    def handle_rollback(message):
        script = _check_script()
        if not script:
            bot.send_message(message.chat.id, "Update script not configured.")
            _show_updates_menu(message)
            return
        logger.info("User %s triggered rollback", message.from_user.first_name)
        bot.reply_to(message, "Rolling back last update...")
        result = run_shell(f"sudo {script} --rollback 2>&1", timeout=300)
        output = result.stdout or result.stderr or "No output."
        for chunk_text in chunk_message(escape_html(output)):
            bot.send_message(message.chat.id, chunk_text)
        _show_updates_menu(message)
