"""System info, stress test, and fan control handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telebot.handler_backends import State, StatesGroup

from linux_server_bot.bot.menus import BTN_BACK_MAIN, BTN_FAN, BTN_STRESS, BTN_SYSINFO, build_action_keyboard
from linux_server_bot.shared.auth import authorized
from linux_server_bot.shared.shell import run_command, run_shell
from linux_server_bot.shared.telegram import chunk_message, escape_html

if TYPE_CHECKING:
    import telebot

    from linux_server_bot.config import AppConfig

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

# Fan state button labels
_BTN_FAN_OFF = "\U0001f4a8 Set fans state 0: Off"
_BTN_FAN_ON = "\U0001f4a8 Set fans state 1: On"


class StressTestStates(StatesGroup):
    waiting_for_duration = State()


def register(bot: telebot.TeleBot, config: AppConfig, show_menu) -> None:
    """Register system info, stress test, and fan control handlers."""

    # --- System Info ---
    @bot.message_handler(func=lambda m: m.text == BTN_SYSINFO)
    @authorized(config)
    def handle_sysinfo(message):
        logger.info("User %s requested system info", message.from_user.first_name)
        bot.reply_to(message, "Getting system info...")
        result = run_shell(_SYSINFO_SCRIPT, timeout=30)
        output = result.stdout or result.stderr
        if output.strip():
            escaped = escape_html(output)
            # Filter out apt path line
            lines = [line for line in escaped.split("\n") if "/usr/bin/apt" not in line]
            text = "<b>System info:</b>\n" + "\n".join(lines)
            for chunk in chunk_message(text):
                bot.send_message(message.chat.id, chunk)
        else:
            bot.send_message(message.chat.id, "No system info available.")
        show_menu(message)

    @bot.message_handler(commands=["sysinfo"])
    @authorized(config)
    def handle_sysinfo_command(message):
        handle_sysinfo(message)

    # --- Stress Test ---
    @bot.message_handler(func=lambda m: m.text == BTN_STRESS)
    @authorized(config)
    def handle_stress_menu(message):
        bot.send_message(message.chat.id, "Enter the number of minutes for the stress test:")
        bot.set_state(message.from_user.id, StressTestStates.waiting_for_duration, message.chat.id)

    @bot.message_handler(state=StressTestStates.waiting_for_duration)
    @authorized(config)
    def handle_stress_input(message):
        bot.delete_state(message.from_user.id, message.chat.id)
        text = message.text.strip()
        if not text.isdigit() or int(text) <= 0:
            bot.send_message(message.chat.id, "Please enter a valid number greater than 0.")
            show_menu(message)
            return
        seconds = int(text) * 60
        bot.send_message(message.chat.id, f"Stress test started for {text} minutes.")
        logger.info("User %s started stress test for %s minutes", message.from_user.first_name, text)
        result = run_command(
            ["stress-ng", "--cpu", "4", "--timeout", f"{seconds}s"],
            timeout=seconds + 30,
        )
        bot.send_message(message.chat.id, f"Stress test finished.\n{result.stdout or result.stderr}")
        show_menu(message)

    # --- Fan Control (direct button matching, no state needed) ---
    @bot.message_handler(func=lambda m: m.text == BTN_FAN)
    @authorized(config)
    def handle_fan_menu(message):
        logger.info("User %s requested fan state", message.from_user.first_name)
        markup = build_action_keyboard([_BTN_FAN_OFF, _BTN_FAN_ON], BTN_BACK_MAIN, row_width=2)
        bot.send_message(message.chat.id, "Choose one of the following options:", reply_markup=markup)

    @bot.message_handler(func=lambda m: m.text and m.text.startswith("\U0001f4a8 Set fans state"))
    @authorized(config)
    def handle_fan_set(message):
        if "state 0" in message.text:
            state = 0
            label = "0: Off (automatic)"
        elif "state 1" in message.text:
            state = 1
            label = "1: On"
        else:
            bot.send_message(message.chat.id, "Invalid option.")
            show_menu(message)
            return

        logger.info("User %s setting fan state to %d", message.from_user.first_name, state)
        bot.send_message(message.chat.id, f"Setting fans state to {label}...")
        result = run_shell(f"echo {state} | sudo tee /sys/class/thermal/cooling_device0/cur_state")
        if result.success:
            bot.send_message(message.chat.id, f"\U0001f4a8 Fans state changed to {label}.")
        else:
            bot.send_message(message.chat.id, f"Setting fans state failed: {result.stderr}")
        show_menu(message)
