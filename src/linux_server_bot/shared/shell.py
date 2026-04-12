"""Safe subprocess wrappers for executing system commands."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30


@dataclass
class ShellResult:
    """Result of a shell command execution."""

    stdout: str
    stderr: str
    returncode: int

    @property
    def success(self) -> bool:
        return self.returncode == 0


def run_command(
    cmd: list[str],
    timeout: int = _DEFAULT_TIMEOUT,
    check: bool = False,
) -> ShellResult:
    """Run a command as a list of arguments (no shell interpolation).

    This is the safe default -- use this for all commands where the arguments
    are known at construction time (systemctl, docker, nc, etherwake, etc.).
    """
    logger.debug("run_command: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )
        result = ShellResult(proc.stdout, proc.stderr, proc.returncode)
    except subprocess.TimeoutExpired:
        logger.warning("Command timed out after %ds: %s", timeout, " ".join(cmd))
        result = ShellResult("", f"Command timed out after {timeout}s", -1)
    except subprocess.CalledProcessError as exc:
        result = ShellResult(exc.stdout or "", exc.stderr or "", exc.returncode)
    except FileNotFoundError:
        logger.error("Command not found: %s", cmd[0])
        result = ShellResult("", f"Command not found: {cmd[0]}", 127)

    logger.debug("run_command result: rc=%d stdout=%d bytes stderr=%d bytes",
                 result.returncode, len(result.stdout), len(result.stderr))
    return result


def run_shell(
    cmd: str,
    timeout: int = _DEFAULT_TIMEOUT,
    check: bool = False,
) -> ShellResult:
    """Run a command string through the shell (shell=True).

    Use this only for commands that require pipes, redirects, or complex shell
    syntax (e.g. system info scripts, user-supplied custom commands).
    """
    logger.debug("run_shell: %s", cmd[:200])
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )
        result = ShellResult(proc.stdout, proc.stderr, proc.returncode)
    except subprocess.TimeoutExpired:
        logger.warning("Shell command timed out after %ds", timeout)
        result = ShellResult("", f"Command timed out after {timeout}s", -1)
    except subprocess.CalledProcessError as exc:
        result = ShellResult(exc.stdout or "", exc.stderr or "", exc.returncode)

    logger.debug("run_shell result: rc=%d stdout=%d bytes stderr=%d bytes",
                 result.returncode, len(result.stdout), len(result.stderr))
    return result
