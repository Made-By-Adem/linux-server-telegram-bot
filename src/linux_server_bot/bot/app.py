"""Bot entrypoint -- initializes the bot, registers handlers, and starts polling."""

from __future__ import annotations

import logging
import os
import time

from dotenv import load_dotenv
from telebot.custom_filters import StateFilter

from linux_server_bot.bot import handlers
from linux_server_bot.bot.callbacks import setup_callback_router
from linux_server_bot.bot.menus import build_main_menu
from linux_server_bot.config import config, load_config, reload_config
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.logging_setup import setup_logging
from linux_server_bot.shared.shell import warmup as shell_warmup
from linux_server_bot.shared.startup import (
    ensure_env,
    print_banner,
    run_preflight_checks,
    setup_graceful_shutdown,
)
from linux_server_bot.shared.telegram import create_bot, escape_html

logger = logging.getLogger(__name__)

# Ordered list of handler modules to register.
# Registration order matters: more specific handlers must come before general ones.
_HANDLER_MODULES = [
    handlers.wol,
    handlers.services,
    handlers.docker,
    handlers.compose,
    handlers.logs,
    handlers.command,
    handlers.servers,
    handlers.sysinfo,
    handlers.security,
    handlers.updates,
    handlers.backups,
    handlers.reboot,
    handlers.scripts,
    handlers.settings,
]


def _write_health_check():
    """Write a health check file for Docker HEALTHCHECK."""
    try:
        with open("/tmp/bot_healthy", "w") as f:
            f.write(str(time.time()))
    except OSError:
        pass


def _start_health_thread():
    """Background thread that updates the health file every 60 seconds."""
    import threading

    def _loop():
        while True:
            _write_health_check()
            time.sleep(60)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()


_HEALTH_POLL_INTERVAL = 5  # seconds between polls
_HEALTH_POLL_TIMEOUT = 300  # give up after 5 minutes


def _get_compose_project() -> str | None:
    """Return the Compose project name for this container, or *None*."""
    from linux_server_bot.shared.shell import run_command

    # The bot's own container knows its compose project via its label.
    result = run_command(
        [
            "docker",
            "inspect",
            "--format",
            '{{index .Config.Labels "com.docker.compose.project"}}',
            "linux-server-bot",
        ],
        timeout=10,
    )
    if result.success and result.stdout.strip():
        return result.stdout.strip()
    return None


def _all_compose_containers_healthy() -> bool:
    """Return True when every container in *this* Compose project is healthy."""
    from linux_server_bot.shared.shell import run_command

    project = _get_compose_project()
    if project is None:
        return False

    # List only containers belonging to the same docker-compose project.
    result = run_command(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label=com.docker.compose.project={project}",
            "--format",
            "{{.Names}}\t{{.Status}}",
        ],
        timeout=10,
    )
    if not result.success:
        return False

    lines = [ln for ln in result.stdout.strip().splitlines() if ln]
    if not lines:
        return False

    return all("(healthy)" in line for line in lines)


def _send_startup_message_when_ready(bot, warmup_thread) -> None:
    """Background thread: waits for warmup + all containers healthy, then notifies."""
    import threading

    def _wait_and_send():
        # Wait for shell warmup so the first user interaction is fast.
        warmup_thread.join(timeout=_HEALTH_POLL_TIMEOUT)

        deadline = time.time() + _HEALTH_POLL_TIMEOUT
        while time.time() < deadline:
            if _all_compose_containers_healthy():
                for chat_id in config.allowed_users:
                    try:
                        bot.send_message(chat_id, "\u2705 Bot is online and ready.")
                    except Exception:
                        logger.warning("Could not send startup message to chat_id=%s", chat_id)
                return
            time.sleep(_HEALTH_POLL_INTERVAL)
        logger.warning("Timed out waiting for all containers to become healthy")

    t = threading.Thread(target=_wait_and_send, daemon=True)
    t.start()


def main() -> None:
    """Main entry point for the bot."""
    load_dotenv()

    # Ensure .env is configured (runs setup wizard on first run)
    env_path = os.path.join(os.getcwd(), ".env")
    ensure_env(env_path)

    # Graceful shutdown on SIGINT/SIGTERM
    setup_graceful_shutdown()

    # Load config (starts watchdog file watcher)
    config_path = os.environ.get("CONFIG_PATH", "config.yaml")
    load_config(config_path)

    # Setup logging
    setup_logging("bot", config.log_directory)
    logger.info("Starting Linux Server Bot v2.0.0")

    # Preflight checks
    checks = run_preflight_checks(config_path, config.bot_token)
    if not checks["bot_token"]:
        logger.error("Cannot start bot without a valid token. Exiting.")
        raise SystemExit(1)

    # Startup banner
    print_banner("Bot", config)

    # Warm up shell detection + Docker CLI in a background thread so the bot
    # starts accepting messages immediately instead of blocking on cold-start
    # commands (nsenter, docker info, systemctl, …).
    import threading

    warmup_thread = threading.Thread(target=shell_warmup, daemon=True, name="shell-warmup")
    warmup_thread.start()

    # Create bot
    bot = create_bot(config.bot_token)
    bot.add_custom_filter(StateFilter(bot))

    # show_menu callback passed to all handlers
    def show_menu(message):
        markup = build_main_menu(config)
        bot.send_message(message.chat.id, "Choose one of the following options:", reply_markup=markup)

    # Register /start and /menu
    @bot.message_handler(commands=["start"])
    @authorized(config)
    def handle_start(message):
        name = escape_html(message.from_user.first_name or "")
        welcome = (
            f"Hey {name}, I'm the Linux Server Bot.\n\n"
            "Hit /menu to see what I can do, or use the commands below:\n\n"
            "<b>Menu</b> - /menu\n"
            "<b>Start</b> - /start"
        )
        markup = build_main_menu(config)
        bot.send_message(message.chat.id, welcome, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(commands=["menu"])
    @authorized(config)
    def handle_menu(message):
        show_menu(message)

    # /reload command
    @bot.message_handler(commands=["reload"])
    @authorized(config)
    def handle_reload(message):
        reload_config(config_path)
        bot.reply_to(message, "\u2705 Config reloaded.")
        show_menu(message)

    # Register all feature handler modules
    for module in _HANDLER_MODULES:
        module.register(bot, config, show_menu)

    # Setup the central callback query router (must be after handler registration)
    setup_callback_router(bot, config)

    # Catch-all handler (must be registered LAST)
    @bot.message_handler(func=lambda m: True)
    def handle_unknown(message):
        if message.chat.id not in config.allowed_users:
            return
        bot.reply_to(message, "I'm sorry, I don't understand that command.")

    logger.info("Bot running...")
    _start_health_thread()

    # Notify all users once warmup is done and every container is healthy.
    _send_startup_message_when_ready(bot, warmup_thread)

    bot.infinity_polling(timeout=30, long_polling_timeout=30)


if __name__ == "__main__":
    main()
