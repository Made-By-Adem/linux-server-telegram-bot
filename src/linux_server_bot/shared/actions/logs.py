"""Log file actions -- shared between bot and API."""

from __future__ import annotations

import logging
import os
import re
from glob import glob

from linux_server_bot.config import config

logger = logging.getLogger(__name__)

_DATE_SUFFIX_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _is_glob(path: str) -> bool:
    return any(c in path for c in ("*", "?", "["))


def _resolve_path(log_path: str) -> list[str]:
    """Resolve a configured log path to concrete file paths."""
    if _is_glob(log_path):
        return sorted(glob(log_path), key=os.path.getmtime, reverse=True)
    if os.path.isdir(log_path):
        files = glob(os.path.join(log_path, "*.log"))
        return [f for f in files if not _DATE_SUFFIX_RE.search(os.path.basename(f))]
    if os.path.isfile(log_path):
        return [log_path]
    return []


def list_available_logs() -> list[dict]:
    """List all configured log paths with their resolved files.

    Returns a flat list: one entry per readable file, each with an
    ``index`` that can be passed to :func:`read_log_tail`.
    """
    entries: list[dict] = []
    idx = 0
    for configured_path in config.logfiles:
        for filepath in _resolve_path(configured_path):
            entries.append({
                "index": idx,
                "path": filepath,
                "name": os.path.basename(filepath),
                "size_bytes": _safe_size(filepath),
            })
            idx += 1
    return entries


def read_log_tail(index: int, tail: int = 50) -> dict:
    """Read the last *tail* lines of log file at *index*.

    The index comes from :func:`list_available_logs`.
    """
    available = list_available_logs()
    if index < 0 or index >= len(available):
        return {"success": False, "error": f"Invalid log index: {index}"}
    filepath = available[index]["path"]
    try:
        with open(filepath) as f:
            lines = f.readlines()
        last = lines[-tail:] if tail else lines
        return {
            "success": True,
            "path": filepath,
            "name": os.path.basename(filepath),
            "total_lines": len(lines),
            "lines_returned": len(last),
            "content": "".join(last),
        }
    except Exception as exc:
        logger.exception("Failed to read log file: %s", filepath)
        return {"success": False, "error": str(exc)}


def _safe_size(path: str) -> int | None:
    try:
        return os.path.getsize(path)
    except OSError:
        return None
