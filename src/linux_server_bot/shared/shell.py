"""Safe subprocess wrappers for executing system commands.

When running inside Docker with ``pid: host``, commands that need access to
host binaries (systemctl, ufw, fail2ban-client, etc.) are automatically
wrapped with ``nsenter -t 1 -m --`` to enter the host's mount namespace.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from functools import lru_cache

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30

# Commands whose binaries are installed in the Docker image and should NOT
# be wrapped with nsenter.  Everything else gets nsenter in Docker mode.
_CONTAINER_LOCAL_COMMANDS = frozenset(
    {
        "docker",
        "nc",
        "python",
        "python3",
        "pip",
        "nsenter",
        "curl",
        "stress-ng",
        "etherwake",
    }
)


@lru_cache(maxsize=1)
def _in_docker() -> bool:
    """Detect if we're running inside a Docker container."""
    return os.path.isfile("/.dockerenv")


@lru_cache(maxsize=1)
def _nsenter_available() -> bool:
    """Check if nsenter and pid:host are available (PID 1 = host init)."""
    if not _in_docker():
        return False
    try:
        proc = subprocess.run(
            ["nsenter", "-t", "1", "-m", "--", "true"],
            capture_output=True,
            timeout=5,
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _needs_nsenter(cmd_name: str) -> bool:
    """Should this command be run via nsenter?"""
    if not _in_docker():
        return False
    # Strip sudo prefix
    if cmd_name == "sudo":
        return True  # Will be handled by wrapping the full command
    return cmd_name not in _CONTAINER_LOCAL_COMMANDS


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

    When running in Docker with pid:host, commands that require host binaries
    are automatically wrapped with ``nsenter -t 1 -m --``.
    """
    # Determine the actual binary (skip sudo to check the real command)
    first_cmd = cmd[0]
    if first_cmd == "sudo" and len(cmd) > 1:
        actual_cmd = cmd[1]
    else:
        actual_cmd = first_cmd

    # Wrap with nsenter if needed
    if _needs_nsenter(actual_cmd) and _nsenter_available():
        cmd = ["nsenter", "-t", "1", "-m", "--"] + cmd
        logger.debug("run_command (nsenter): %s", " ".join(cmd))
    else:
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

    logger.debug(
        "run_command result: rc=%d stdout=%d bytes stderr=%d bytes",
        result.returncode,
        len(result.stdout),
        len(result.stderr),
    )
    return result


def run_shell(
    cmd: str,
    timeout: int = _DEFAULT_TIMEOUT,
    check: bool = False,
) -> ShellResult:
    """Run a command string through the shell (shell=True).

    Use this only for commands that require pipes, redirects, or complex shell
    syntax (e.g. system info scripts, user-supplied custom commands).

    When running in Docker with pid:host, the command is automatically wrapped
    with ``nsenter -t 1 -m --`` to run in the host's mount namespace.
    """
    if _in_docker() and _nsenter_available():
        cmd = f"nsenter -t 1 -m -- sh -c {_shell_quote(cmd)}"
        logger.debug("run_shell (nsenter): %s", cmd[:200])
    else:
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

    logger.debug(
        "run_shell result: rc=%d stdout=%d bytes stderr=%d bytes",
        result.returncode,
        len(result.stdout),
        len(result.stderr),
    )
    return result


def warmup() -> None:
    """Pre-warm cached checks, Docker CLI, nsenter, and common host tools.

    Call once at startup so the first user interaction doesn't pay the
    cold-start cost of nsenter detection, Docker daemon handshake,
    systemctl, journalctl, or other common commands used by handlers.

    All warm-up commands run in parallel to minimise total wall-clock time.
    """
    import concurrent.futures

    # 1. Populate lru_cache for runtime detection (must finish before the
    #    parallel phase because run_command reads these caches).
    _in_docker()
    _nsenter_available()

    # 2. Fire off warm-up commands concurrently.
    nsenter_ok = _nsenter_available()

    # Commands that only make sense when nsenter is available (host tools).
    host_cmds: list[tuple[list[str], int]] = []
    if nsenter_ok:
        host_cmds = [
            # systemctl (services handler)
            (["systemctl", "is-active", "docker"], 10),
            (["systemctl", "list-units", "--type=service", "--state=running",
              "--no-legend", "--no-pager", "--plain"], 15),
            # journalctl (security handler -- failed logins)
            (["journalctl", "--no-pager", "-n", "1"], 10),
            # Basic host tools used by sysinfo
            (["hostname"], 5),
            (["who"], 5),
        ]

    # Commands that run inside the container (Docker CLI).
    docker_cmds: list[tuple[list[str], int]] = [
        (["docker", "info", "-f", "{{.ID}}"], 15),
        (["docker", "ps", "-a", "--format", "{{.Names}}"], 15),
    ]

    all_cmds = docker_cmds + host_cmds

    def _run(args_timeout):
        cmd, timeout = args_timeout
        try:
            run_command(cmd, timeout=timeout)
        except Exception:
            logger.debug("Warmup command failed (non-fatal): %s", " ".join(cmd))

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(all_cmds) or 1) as pool:
        list(pool.map(_run, all_cmds))

    logger.debug("Shell warmup complete")


def _shell_quote(s: str) -> str:
    """Quote a string for safe shell embedding in single quotes."""
    return "'" + s.replace("'", "'\"'\"'") + "'"
