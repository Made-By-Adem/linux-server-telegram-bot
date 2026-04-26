"""Pironman 5 / 5 Max actions -- fan modes, RGB LED control, fan LED, OLED sleep."""

from __future__ import annotations

import logging

from linux_server_bot.shared.shell import run_command

logger = logging.getLogger(__name__)

FAN_MODES = {
    "0": "Always on",
    "1": "Performance (> 50°C)",
    "2": "Cool (> 60°C)",
    "3": "Balanced (> 67.5°C)",
    "4": "Quiet (> 70°C)",
}

LED_STYLES = [
    "solid",
    "breathing",
    "flow",
    "flow_reverse",
    "rainbow",
    "rainbow_reverse",
    "hue_cycle",
]

FAN_LED_MODES = ["on", "off", "follow"]


def _run_pironman(args: list[str]) -> dict:
    result = run_command(["sudo", "pironman5"] + args, timeout=15)
    if result.success:
        restart = run_command(
            ["sudo", "systemctl", "restart", "pironman5.service"],
            timeout=15,
        )
        if not restart.success:
            logger.warning("Failed to restart pironman5.service: %s", restart.stderr.strip())
    return {
        "success": result.success,
        "output": result.stdout.strip() if result.success else "",
        "error": result.stderr.strip() if not result.success else "",
    }


def is_available() -> bool:
    result = run_command(["which", "pironman5"], timeout=5)
    return result.success and bool(result.stdout.strip())


def get_config() -> dict:
    result = run_command(["sudo", "pironman5", "-c"], timeout=10)
    return {
        "success": result.success,
        "output": (result.stdout or result.stderr).strip(),
    }


def set_fan_mode(mode: str) -> dict:
    if mode not in FAN_MODES:
        return {"success": False, "error": f"Invalid fan mode: {mode}"}
    return _run_pironman(["-gm", mode])


def set_rgb_enabled(enabled: bool) -> dict:
    return _run_pironman(["-re", str(enabled)])


def set_rgb_color(hex_code: str) -> dict:
    hex_code = hex_code.lstrip("#")
    if len(hex_code) != 6 or not all(c in "0123456789abcdefABCDEF" for c in hex_code):
        return {"success": False, "error": "Invalid hex color code"}
    return _run_pironman(["-rc", hex_code])


def set_rgb_style(style: str) -> dict:
    if style not in LED_STYLES:
        return {"success": False, "error": f"Invalid LED style: {style}"}
    return _run_pironman(["-rs", style])


def set_rgb_speed(speed: int) -> dict:
    if not (0 <= speed <= 100):
        return {"success": False, "error": "Speed must be between 0 and 100"}
    return _run_pironman(["-rp", str(speed)])


def set_rgb_brightness(brightness: int) -> dict:
    if not (0 <= brightness <= 100):
        return {"success": False, "error": "Brightness must be between 0 and 100"}
    return _run_pironman(["-rb", str(brightness)])


# -- Max-only features --


def set_fan_led(mode: str) -> dict:
    if mode not in FAN_LED_MODES:
        return {"success": False, "error": f"Invalid fan LED mode: {mode}"}
    return _run_pironman(["-fl", mode])


def set_oled_sleep(seconds: int) -> dict:
    if not (5 <= seconds <= 600):
        return {"success": False, "error": "OLED sleep must be between 5 and 600 seconds"}
    return _run_pironman(["-os", str(seconds)])
