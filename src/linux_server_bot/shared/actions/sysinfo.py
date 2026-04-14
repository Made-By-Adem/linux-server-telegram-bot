"""System info actions -- shared between bot and API."""

from __future__ import annotations

import logging

from linux_server_bot.shared.shell import run_command, run_shell

logger = logging.getLogger(__name__)

_SYSINFO_SCRIPT = r"""
# CPU
cpu=$(top -b -n 1 | awk '/^%Cpu/ {printf "%.1f", 100 - $8}')
echo "CPU|${cpu}%"

# Memory
free -m | awk '/^Mem/ {printf "MEM|%dMB|%dMB|%dMB|%dMB\n", $2, $3, $4, $6}'

# Disk
df -h 2>/dev/null | grep /dev/ | awk '{printf "DISK|%s|%s|%s|%s|%s\n", $6, $2, $3, $4, $5}'

# Temperature
temp=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
if [ -n "$temp" ]; then echo "TEMP|$(echo "$temp" | awk '{printf "%.1f", $1/1000}')"; else echo "TEMP|N/A"; fi

# Fan
fan=$(cat /sys/class/thermal/cooling_device0/cur_state 2>/dev/null)
if [ -n "$fan" ]; then echo "FAN|${fan}"; else echo "FAN|N/A"; fi

# Updates
if command -v apt &> /dev/null; then
  count=$(apt list --upgradable 2>/dev/null | grep -c '/' || true)
  echo "UPD|${count}"
else
  echo "UPD|N/A"
fi

# Uptime
echo "UP|$(uptime -p 2>/dev/null || uptime)"

# Hostname
echo "HOST|$(hostname)"
"""


def get_sysinfo_text() -> str:
    """Get full system info as structured, formatted text."""
    result = run_shell(_SYSINFO_SCRIPT, timeout=30)
    if not result.stdout.strip():
        return result.stderr or "Could not retrieve system info."

    lines = {}
    for line in result.stdout.strip().split("\n"):
        if "|" in line:
            parts = line.split("|", 1)
            key = parts[0].strip()
            val = parts[1].strip() if len(parts) > 1 else ""
            if key == "DISK":
                lines.setdefault("DISK", []).append(val)
            else:
                lines[key] = val

    out = []

    # Header
    hostname = lines.get("HOST", "Server")
    out.append(f"\U0001f5a5 {hostname}")
    out.append("")

    # CPU
    cpu = lines.get("CPU", "N/A")
    out.append(f"\U0001f4c8 CPU: {cpu}")

    # Memory
    mem = lines.get("MEM", "")
    if mem:
        parts = mem.split("|")
        if len(parts) == 4:
            out.append(f"\U0001f9e0 Memory: {parts[1]} / {parts[0]} used ({parts[3]} cache)")

    # Temperature
    temp = lines.get("TEMP", "N/A")
    if temp != "N/A":
        out.append(f"\U0001f321 Temperature: {temp}\u00b0C")

    # Fan
    fan = lines.get("FAN", "N/A")
    if fan != "N/A":
        fan_label = "off (auto)" if fan == "0" else "on"
        out.append(f"\U0001f4a8 Fan: {fan_label}")

    out.append("")

    # Disk
    disks = lines.get("DISK", [])
    if disks:
        out.append("\U0001f4be Disk:")
        for d in disks:
            parts = d.split("|")
            if len(parts) == 5:
                mount, total, used, free, pct = parts
                out.append(f"  {mount}: {used}/{total} ({pct}) \u2014 {free} free")

    out.append("")

    # Updates
    upd = lines.get("UPD", "N/A")
    if upd != "N/A":
        upd_icon = "\u2705" if upd == "0" else "\U0001f4e6"
        upd_text = "up to date" if upd == "0" else f"{upd} available"
        out.append(f"{upd_icon} Updates: {upd_text}")

    # Uptime
    uptime_str = lines.get("UP", "N/A")
    out.append(f"\u23f1 Uptime: {uptime_str}")

    return "\n".join(out)


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
            "total_mb": int(parts[0]),
            "used_mb": int(parts[1]),
            "free_mb": int(parts[2]),
            "cache_mb": int(parts[3]),
            "success": True,
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
                partitions.append(
                    {
                        "device": parts[0],
                        "total": parts[1],
                        "used": parts[2],
                        "free": parts[3],
                        "percent": parts[4],
                    }
                )
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
