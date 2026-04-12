"""System info actions -- shared between bot and API."""

from __future__ import annotations

import logging

from linux_server_bot.shared.shell import run_command, run_shell

logger = logging.getLogger(__name__)

_SYSINFO_SCRIPT = """
echo "CPU Usage:"
top -b -n 1 | awk '/^%Cpu/ {print "Usage: " 100 - $8 "%"}'

echo "\\nMemory Usage:"
free -m | awk '/^Mem/ {print "Total: " $2 "MB\\tUsed: " $3 "MB\\tFree: " $4 "MB\\tCache: " $6 "MB"}'

echo "\\nDisk Usage (Total, Used, Free):"
df -h 2>/dev/null | grep /dev/ | awk '{print "Total: " $2 "\\tUsed: " $3 " (" $5 ") \\tFree: " $4}'

echo "\\nCurrent Temperature:"
cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{print "Temperature: " $1/1000 "°C"}' || echo "N/A"

echo "\\nCurrent Fan state:"
cat /sys/class/thermal/cooling_device0/cur_state 2>/dev/null | awk '{print "Fan state: " $1}' || echo "N/A"

echo "\\nAvailable Updates:"
if command -v apt &> /dev/null; then
  sudo apt list --upgradable 2>/dev/null | grep -c '/'
elif command -v yum &> /dev/null; then
  sudo yum list updates 2>/dev/null | grep -c '\\.'
else
  echo "Unsupported package manager"
fi

echo "\\nSystem Uptime:"
uptime
"""


def get_sysinfo_text() -> str:
    """Get full system info as formatted text."""
    result = run_shell(_SYSINFO_SCRIPT, timeout=30)
    output = result.stdout or result.stderr
    if output.strip():
        return "\n".join(line for line in output.split("\n") if "/usr/bin/apt" not in line)
    return ""


def get_cpu_usage() -> dict:
    """Get CPU usage percentage."""
    result = run_shell("top -bn 1 | awk '/^%Cpu/ {print 100 - $8}'")
    try:
        return {"cpu_percent": float(result.stdout.strip()), "success": True}
    except (ValueError, IndexError):
        return {"cpu_percent": None, "success": False, "error": "Could not parse CPU usage"}


def get_memory_usage() -> dict:
    """Get memory usage."""
    result = run_shell("free -m | awk '/^Mem/ {print $2,$3,$4,$6}'")
    try:
        parts = result.stdout.strip().split()
        return {
            "total_mb": int(parts[0]), "used_mb": int(parts[1]),
            "free_mb": int(parts[2]), "cache_mb": int(parts[3]), "success": True,
        }
    except (ValueError, IndexError):
        return {"success": False, "error": "Could not parse memory info"}


def get_disk_usage() -> dict:
    """Get disk usage for all partitions."""
    result = run_shell("df -h 2>/dev/null | grep /dev/ | awk '{print $1,$2,$3,$4,$5,$6}'")
    partitions = []
    for line in result.stdout.strip().split("\n"):
        if line:
            parts = line.split()
            if len(parts) >= 5:
                partitions.append({
                    "device": parts[0], "total": parts[1], "used": parts[2],
                    "free": parts[3], "percent": parts[4],
                })
    return {"partitions": partitions, "success": True}


def get_temperature() -> dict:
    """Get system temperature."""
    result = run_shell("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
    try:
        temp_c = int(result.stdout.strip()) / 1000
        return {"temperature_celsius": temp_c, "success": True}
    except (ValueError, IndexError):
        return {"temperature_celsius": None, "success": False, "error": "Could not read temperature"}


def set_fan_state(state: int) -> dict:
    """Set fan state (0=off/auto, 1=on)."""
    result = run_shell(f"echo {state} | sudo tee /sys/class/thermal/cooling_device0/cur_state")
    return {"state": state, "success": result.success, "error": result.stderr if not result.success else ""}


def run_stress_test(minutes: int) -> dict:
    """Run a CPU stress test."""
    seconds = minutes * 60
    result = run_command(
        ["stress-ng", "--cpu", "4", "--timeout", f"{seconds}s"],
        timeout=seconds + 30,
    )
    return {"minutes": minutes, "success": result.success, "output": result.stdout or result.stderr}
