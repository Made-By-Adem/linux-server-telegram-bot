#!/usr/bin/env python3
"""One-time migration tool: convert existing .txt/.env config files to config.yaml."""

from __future__ import annotations

import os
import sys

import yaml


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Read .env for defaults
    env_vars = {}
    env_path = os.path.join(base, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    env_vars[key.strip()] = val.strip()

    def read_txt(path: str) -> list[str]:
        full = os.path.join(base, path)
        if not os.path.exists(full):
            return []
        with open(full) as f:
            return [line.strip() for line in f if line.strip()]

    def parse_servers(lines: list[str]) -> list[dict]:
        servers = []
        for line in lines:
            if "=" not in line:
                continue
            name, _, addr = line.partition("=")
            host, _, port = addr.partition(":")
            servers.append({
                "name": name.strip(),
                "host": host.strip(),
                "port": int(port.strip()) if port.strip() else 443,
            })
        return servers

    # Read all config sources
    bot_services = read_txt("linux_bot/bot_services.txt")
    bot_logfiles = read_txt("linux_bot/bot_logfiles.txt")
    bot_servers_raw = read_txt("linux_bot/bot_servers.txt")
    mon_services = read_txt("linux_monitoring/monitoring_services.txt")
    mon_containers = read_txt("linux_monitoring/monitoring_containers.txt")
    mon_servers_raw = read_txt("linux_monitoring/monitoring_servers.txt")

    bot_servers = parse_servers(bot_servers_raw)
    mon_servers = parse_servers(mon_servers_raw)

    config = {
        "telegram": {
            "bot_token": "${SECRET_TOKEN}",
            "allowed_users": ["${CHAT_ID_PERSON1}"],
        },
        "wol": {
            "address": "${WOL_ADDRESS}",
            "hostname": "${WOL_HOSTNAME}",
            "interface": "eth0",
        },
        "features": {
            "systemd_services": True,
            "docker_containers": True,
            "docker_compose": True,
            "custom_commands": True,
            "wol": True,
            "security_overview": True,
            "backups": True,
            "container_updates": True,
            "logs": True,
            "server_ping": True,
            "system_info": True,
            "stress_test": True,
            "fan_control": True,
            "reboot": True,
        },
        "services": bot_services,
        "containers": [],
        "compose_stacks": [],
        "servers": bot_servers,
        "logfiles": bot_logfiles,
        "scripts": {
            "update_containers": "",
            "backup": "",
        },
        "server_states_path": "server_states.json",
        "log_directory": "./logs",
        "monitoring": {
            "interval_minutes": 5,
            "containers": mon_containers,
            "servers": mon_servers,
            "services": mon_services,
            "thresholds": {
                "cpu_percent": 80,
                "storage_percent": 90,
                "temperature_celsius": 50,
            },
            "security": {
                "check_fail2ban": True,
                "check_ufw": True,
                "check_ssh_sessions": True,
            },
        },
    }

    output = os.path.join(base, "config.yaml")
    with open(output, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"Config written to {output}")
    print("Review the file and adjust values as needed.")
    print("Remember to keep your .env file for SECRET_TOKEN, CHAT_ID, and WOL variables.")


if __name__ == "__main__":
    main()
