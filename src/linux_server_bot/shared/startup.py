"""Shared startup utilities: setup wizard, preflight checks, and helpers.

Used by both the bot and API entrypoints to ensure a smooth first-run
experience and robust error handling on every subsequent start.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import signal
import socket
import sys
import tempfile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PLACEHOLDER_VALUES = {
    "your_telebot_token",
    "your_telegram_chat_id",
    "your_mac_address_in_same_network_as_server",
    "your_hostname",
    "your-secret-api-key-here",
    "your-api-key-here",
    "changeme",
}

_SETUP_STATE_FILE = ".setup_state.json"


# ---------------------------------------------------------------------------
# Atomic file writes
# ---------------------------------------------------------------------------


def atomic_write(path: str, content: str) -> None:
    """Write *content* to *path* atomically via a temp file + rename.

    If the process is interrupted mid-write the original file stays intact.
    """
    dir_name = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix=".tmp_", suffix=".env")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp_path, path)  # atomic on POSIX
    except BaseException:
        # Clean up temp file on any failure (including KeyboardInterrupt)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Setup state tracking (resume support)
# ---------------------------------------------------------------------------


def _state_path() -> str:
    return os.path.join(os.getcwd(), _SETUP_STATE_FILE)


def load_setup_state() -> dict:
    """Load the setup state file, or return empty dict."""
    path = _state_path()
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_setup_state(state: dict) -> None:
    """Persist setup state atomically."""
    atomic_write(_state_path(), json.dumps(state, indent=2) + "\n")


def mark_step_done(step: str) -> None:
    """Mark a setup step as completed."""
    state = load_setup_state()
    state[step] = True
    save_setup_state(state)


def is_step_done(step: str) -> bool:
    """Check if a setup step was already completed."""
    return load_setup_state().get(step, False)


# ---------------------------------------------------------------------------
# .env helpers
# ---------------------------------------------------------------------------


def _read_env(env_path: str) -> str:
    """Read .env file contents, or empty string if missing."""
    if os.path.exists(env_path):
        with open(env_path) as f:
            return f.read()
    return ""


def _get_env_value(content: str, key: str) -> str:
    """Extract the value for *key* from .env content."""
    for line in content.splitlines():
        stripped = line.split("#")[0].strip()
        if stripped.startswith(f"{key}="):
            return stripped.split("=", 1)[1].strip()
    return ""


def _set_env_value(content: str, key: str, value: str) -> str:
    """Set or replace a key=value pair in .env content."""
    lines = content.splitlines(keepends=True)
    replaced = False
    for i, line in enumerate(lines):
        stripped = line.split("#")[0].strip()
        if stripped.startswith(f"{key}="):
            # Preserve any comment on the same line
            lines[i] = f"{key}={value}\n"
            replaced = True
            break
    if not replaced:
        if content and not content.endswith("\n"):
            lines.append("\n")
        lines.append(f"{key}={value}\n")
    return "".join(lines)


def _is_placeholder(value: str) -> bool:
    """Check if a value is empty or a known placeholder."""
    return not value.strip() or value.strip() in _PLACEHOLDER_VALUES


# ---------------------------------------------------------------------------
# First-run setup wizard
# ---------------------------------------------------------------------------


def _prompt(question: str, default: str = "") -> str:
    """Ask user for input. Returns default on EOF/interrupt."""
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"{question}{suffix}: ").strip()
        return answer if answer else default
    except (EOFError, KeyboardInterrupt):
        print()
        return default


def _is_interactive() -> bool:
    """Check if stdin is a terminal (not piped/Docker)."""
    return sys.stdin.isatty()


def run_setup_wizard(env_path: str) -> None:
    """Interactive first-run wizard for .env configuration.

    Each step is tracked in .setup_state.json so an interrupted setup
    can be resumed from where it left off.
    """
    content = _read_env(env_path)
    changed = False

    print("\n" + "=" * 60)
    print("  Linux Server Bot - First-Run Setup")
    print("=" * 60)

    state = load_setup_state()
    if state:
        print("\n  Resuming setup from where you left off...\n")
    else:
        print("\n  Let's configure the essentials to get your bot running.\n")

    # Step 1: Bot token (required)
    if not is_step_done("bot_token"):
        current = _get_env_value(content, "SECRET_TOKEN")
        if _is_placeholder(current):
            print("Step 1/4: Telegram Bot Token")
            print("  Get one from @BotFather on Telegram: https://t.me/BotFather")
            print("  Send /newbot, follow the prompts, and paste the token here.\n")
            token = _prompt("  Bot token")
            if token and token not in _PLACEHOLDER_VALUES:
                content = _set_env_value(content, "SECRET_TOKEN", token)
                os.environ["SECRET_TOKEN"] = token
                changed = True
                mark_step_done("bot_token")
                print("  ✓ Bot token saved.\n")
            else:
                print("  ⚠ Skipped. You can set SECRET_TOKEN in .env later.\n")
        else:
            mark_step_done("bot_token")

    # Step 2: Chat ID (required)
    if not is_step_done("chat_id"):
        current = _get_env_value(content, "CHAT_ID_PERSON1")
        if _is_placeholder(current):
            print("Step 2/4: Your Telegram Chat ID")
            print("  Get it from @RawDataBot on Telegram: https://t.me/raw_data_bot")
            print("  Send /start and copy the chat_id number.\n")
            chat_id = _prompt("  Chat ID")
            if chat_id and chat_id not in _PLACEHOLDER_VALUES:
                content = _set_env_value(content, "CHAT_ID_PERSON1", chat_id)
                os.environ["CHAT_ID_PERSON1"] = chat_id
                changed = True
                mark_step_done("chat_id")
                print("  ✓ Chat ID saved.\n")
            else:
                print("  ⚠ Skipped. You can set CHAT_ID_PERSON1 in .env later.\n")
        else:
            mark_step_done("chat_id")

    # Step 3: API key (auto-generated)
    if not is_step_done("api_key"):
        current = _get_env_value(content, "API_KEY")
        if _is_placeholder(current):
            new_key = secrets.token_urlsafe(32)
            content = _set_env_value(content, "API_KEY", new_key)
            os.environ["API_KEY"] = new_key
            changed = True
            print("Step 3/4: API Key")
            print(f"  ✓ Generated automatically: {new_key[:12]}...")
            print("  Stored in .env. Use this key for HTTP API access.\n")
        mark_step_done("api_key")

    # Step 4: WoL (optional)
    if not is_step_done("wol"):
        current = _get_env_value(content, "WOL_ADDRESS")
        if _is_placeholder(current):
            print("Step 4/4: Wake-on-LAN (optional)")
            print("  If you have a device to wake via LAN, enter its MAC address.")
            print("  Press Enter to skip.\n")
            mac = _prompt("  MAC address (e.g. aa:bb:cc:dd:ee:ff)")
            if mac and mac not in _PLACEHOLDER_VALUES:
                content = _set_env_value(content, "WOL_ADDRESS", mac)
                hostname = _prompt("  Device hostname", "my-device")
                content = _set_env_value(content, "WOL_HOSTNAME", hostname)
                changed = True
                print("  ✓ WoL settings saved.\n")
            else:
                print("  ⚠ Skipped. You can configure WoL in .env later.\n")
        mark_step_done("wol")

    # Write .env atomically
    if changed:
        atomic_write(env_path, content)
        print("  ✓ Configuration saved to .env")

    print("=" * 60)
    print("  Setup complete! Starting the bot...\n")


def ensure_env(env_path: str) -> None:
    """Ensure .env exists and has required values.

    In interactive mode: runs the setup wizard for missing values.
    In non-interactive mode: generates API key silently, skips the rest.
    """
    content = _read_env(env_path)
    needs_setup = (
        not os.path.exists(env_path)
        or _is_placeholder(_get_env_value(content, "SECRET_TOKEN"))
        or _is_placeholder(_get_env_value(content, "CHAT_ID_PERSON1"))
    )

    # Check if setup was started but not finished
    state = load_setup_state()
    setup_incomplete = state and not all(state.get(s) for s in ("bot_token", "chat_id", "api_key", "wol"))

    if (needs_setup or setup_incomplete) and _is_interactive():
        run_setup_wizard(env_path)
        return

    # Non-interactive: just ensure API key exists
    changed = False
    current_key = _get_env_value(content, "API_KEY")
    if _is_placeholder(current_key):
        new_key = secrets.token_urlsafe(32)
        content = _set_env_value(content, "API_KEY", new_key)
        os.environ["API_KEY"] = new_key
        changed = True
        logger.info("Generated new API key and saved to .env")

    if changed:
        atomic_write(env_path, content)


# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------


def check_bot_token(token: str) -> bool:
    """Validate a Telegram bot token by calling getMe.

    Returns True if valid, False otherwise.
    """
    if not token or token in _PLACEHOLDER_VALUES:
        logger.error(
            "Bot token is not configured. Set SECRET_TOKEN in .env (get one from @BotFather: https://t.me/BotFather)"
        )
        return False

    import telebot

    try:
        bot = telebot.TeleBot(token)
        me = bot.get_me()
        logger.info("Bot token valid: @%s", me.username)
        return True
    except telebot.apihelper.ApiTelegramException as e:
        logger.error("Bot token is invalid: %s", e)
        return False
    except Exception as e:
        logger.warning("Could not validate bot token (network issue?): %s", e)
        # Don't block startup on network errors — token might still be valid
        return True


def check_docker_socket() -> bool:
    """Check if the Docker socket is accessible."""
    sock_path = "/var/run/docker.sock"
    if os.path.exists(sock_path):
        if os.access(sock_path, os.R_OK | os.W_OK):
            return True
        logger.warning("Docker socket exists but is not readable/writable. Docker features may not work.")
        return False
    logger.info(
        "Docker socket not found at %s. Docker features will not work (this is normal if Docker is not installed).",
        sock_path,
    )
    return False


def check_config_file(config_path: str) -> bool:
    """Check if config.yaml exists."""
    if os.path.exists(config_path):
        return True
    logger.warning(
        "Config file %s not found. Using defaults. Copy config.example.yaml to config.yaml to customize.",
        config_path,
    )
    return False


def run_preflight_checks(config_path: str, token: str) -> dict:
    """Run all preflight checks and return results dict."""
    results = {
        "config_file": check_config_file(config_path),
        "bot_token": check_bot_token(token),
        "docker_socket": check_docker_socket(),
    }
    return results


# ---------------------------------------------------------------------------
# Port management (for API)
# ---------------------------------------------------------------------------


def is_port_free(port: int) -> bool:
    """Check if a port is available on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def find_free_port(preferred: int, max_attempts: int = 20) -> int | None:
    """Return *preferred* if free, otherwise try the next ports.

    After *max_attempts* failures, ask the user for a port interactively.
    Returns ``None`` if the user chooses to skip the API.
    """
    for offset in range(max_attempts):
        candidate = preferred + offset
        if is_port_free(candidate):
            if offset > 0:
                logger.warning(
                    "Port %d is in use, using %d instead",
                    preferred,
                    candidate,
                )
            return candidate

    # All automatic attempts exhausted — ask the user
    print(f"\nPorts {preferred}-{preferred + max_attempts - 1} are all in use.")
    if _is_interactive():
        try:
            answer = input("Enter a port number to use, or press Enter to skip the API: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None

        if not answer:
            return None

        try:
            port = int(answer)
        except ValueError:
            print(f"'{answer}' is not a valid port number. Skipping API.")
            return None

        if is_port_free(port):
            return port
        print(f"Port {port} is also in use. Skipping API.")
        return None

    # Non-interactive — skip
    return None


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------


def setup_graceful_shutdown() -> None:
    """Install signal handlers for clean shutdown (no stack traces)."""

    def _handler(signum, frame):
        sig_name = signal.Signals(signum).name
        print(f"\n{sig_name} received, shutting down...")
        logger.info("Shutdown signal received: %s", sig_name)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


# ---------------------------------------------------------------------------
# Startup banner
# ---------------------------------------------------------------------------


def print_banner(service: str, config) -> None:
    """Print a startup summary showing what's active."""
    lines = [
        "",
        "=" * 50,
        f"  Linux Server Bot - {service}",
        "=" * 50,
        "",
    ]

    if service in ("Bot", "All"):
        enabled = []
        disabled = []
        features = config.features
        feature_names = {
            "systemd_services": "Services",
            "docker_containers": "Docker",
            "docker_compose": "Compose",
            "custom_commands": "Commands",
            "wol": "Wake-on-LAN",
            "security_overview": "Security",
            "backups": "Backups",
            "container_updates": "Updates",
            "logs": "Logs",
            "server_ping": "Server Ping",
            "system_info": "System Info",
            "stress_test": "Stress Test",
            "fan_control": "Fan Control",
            "reboot": "Reboot",
        }
        for attr, label in feature_names.items():
            if getattr(features, attr, False):
                enabled.append(label)
            else:
                disabled.append(label)

        lines.append(f"  Features: {', '.join(enabled)}")
        if disabled:
            lines.append(f"  Disabled: {', '.join(disabled)}")
        lines.append(f"  Allowed users: {len(config.allowed_users)}")

    if service in ("Monitoring", "All"):
        m = config.monitoring
        lines.append(f"  Monitoring: every {m.interval_minutes} min")
        lines.append(f"    Containers: {', '.join(c.name for c in config.containers) or 'none'}")
        lines.append(f"    Services: {', '.join(s.name for s in config.services) or 'none'}")
        lines.append(f"    Servers: {len(m.servers)}")
        lines.append(
            f"    Thresholds: CPU {m.thresholds.get('cpu_percent', 80)}% / "
            f"Disk {m.thresholds.get('storage_percent', 90)}% / "
            f"Temp {m.thresholds.get('temperature_celsius', 50)}°C"
        )

    if service in ("API", "All"):
        lines.append(f"  API: {'enabled' if config.api.enabled else 'disabled'}")
        if config.api.enabled:
            lines.append(f"    Port: {config.api.port}")
            lines.append(f"    Docs: http://127.0.0.1:{config.api.port}/docs")

    lines.extend(["", "=" * 50, ""])

    for line in lines:
        print(line)
