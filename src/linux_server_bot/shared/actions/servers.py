"""Server ping actions -- shared between bot and API."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time

from linux_server_bot.shared.shell import run_command

logger = logging.getLogger(__name__)


def load_server_states(path: str) -> dict[str, str]:
    """Load server states from JSON file."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_server_states(path: str, states: dict[str, str]) -> None:
    """Atomic write server states to JSON."""
    dir_name = os.path.dirname(path) or "."
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(states, f)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def ping_server(host: str, port: int, timeout: int = 5) -> bool:
    """Ping a server using netcat. Returns True if reachable."""
    result = run_command(["nc", "-zv", "-w", str(timeout), host, str(port)], timeout=timeout + 5)
    output = result.stdout + result.stderr
    return "succeeded" in output or "open" in output


def ping_server_with_retry(name: str, host: str, port: int) -> dict:
    """Ping a server with retry logic. Returns status dict."""
    if ping_server(host, port):
        return {"name": name, "host": host, "port": port, "status": "online"}

    time.sleep(5)
    if ping_server(host, port, timeout=10):
        return {"name": name, "host": host, "port": port, "status": "online"}

    return {"name": name, "host": host, "port": port, "status": "offline"}
