"""YAML configuration loader with watchdog hot-reload and environment variable interpolation."""

from __future__ import annotations

import logging
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path("config.yaml")
_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")
_DEBOUNCE_SECONDS = 0.5


def _interpolate_env(value: Any) -> Any:
    """Recursively replace ${VAR} patterns with environment variable values."""
    if isinstance(value, str):
        def _replacer(match: re.Match) -> str:
            var = match.group(1)
            env_val = os.environ.get(var, "")
            if not env_val:
                logger.warning("Environment variable %s is not set", var)
            return env_val
        return _ENV_VAR_PATTERN.sub(_replacer, value)
    if isinstance(value, dict):
        return {k: _interpolate_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(item) for item in value]
    return value


@dataclass
class ServerEntry:
    name: str
    host: str
    port: int = 443


@dataclass
class ComposeStack:
    name: str
    path: str


@dataclass
class MonitoringConfig:
    interval_minutes: int = 5
    containers: list[str] = field(default_factory=list)
    servers: list[ServerEntry] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    thresholds: dict[str, int | float] = field(default_factory=lambda: {
        "cpu_percent": 80,
        "storage_percent": 90,
        "temperature_celsius": 50,
    })
    security: dict[str, bool] = field(default_factory=lambda: {
        "check_fail2ban": True,
        "check_ufw": True,
        "check_ssh_sessions": True,
    })


@dataclass
class WolConfig:
    address: str = ""
    hostname: str = ""
    interface: str = "eth0"


@dataclass
class FeaturesConfig:
    systemd_services: bool = True
    docker_containers: bool = True
    docker_compose: bool = True
    custom_commands: bool = True
    wol: bool = True
    security_overview: bool = True
    backups: bool = True
    container_updates: bool = True
    logs: bool = True
    server_ping: bool = True
    system_info: bool = True
    stress_test: bool = True
    fan_control: bool = True
    reboot: bool = True


@dataclass
class ApiConfig:
    enabled: bool = False
    port: int = 8120
    api_key: str = ""


@dataclass
class ScriptsConfig:
    update_containers: str = ""
    backup: str = ""


@dataclass
class AppConfig:
    """Central application configuration, loaded from YAML."""

    bot_token: str = ""
    allowed_users: list[int] = field(default_factory=list)
    wol: WolConfig = field(default_factory=WolConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    services: list[str] = field(default_factory=list)
    containers: list[str] = field(default_factory=list)
    compose_stacks: list[ComposeStack] = field(default_factory=list)
    servers: list[ServerEntry] = field(default_factory=list)
    logfiles: list[str] = field(default_factory=list)
    scripts: ScriptsConfig = field(default_factory=ScriptsConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    server_states_path: str = "server_states.json"
    log_directory: str = "./logs"

    def update_from_dict(self, data: dict[str, Any]) -> None:
        """Update config fields from a parsed YAML dict."""
        telegram = data.get("telegram", {})
        self.bot_token = telegram.get("bot_token", os.environ.get("SECRET_TOKEN", self.bot_token))
        raw_users = telegram.get("allowed_users", [])
        self.allowed_users = [int(u) for u in raw_users if u]

        wol = data.get("wol", {})
        self.wol = WolConfig(
            address=str(wol.get("address", "")),
            hostname=str(wol.get("hostname", "")),
            interface=str(wol.get("interface", "eth0")),
        )

        features = data.get("features", {})
        self.features = FeaturesConfig(**{
            k: v for k, v in features.items()
            if k in FeaturesConfig.__dataclass_fields__
        }) if features else FeaturesConfig()

        self.services = data.get("services", [])
        self.containers = data.get("containers", [])
        self.logfiles = data.get("logfiles", [])
        self.server_states_path = data.get("server_states_path", "server_states.json")
        self.log_directory = data.get("log_directory", "./logs")

        # Compose stacks
        self.compose_stacks = [
            ComposeStack(name=s["name"], path=s["path"])
            for s in data.get("compose_stacks", [])
            if "name" in s and "path" in s
        ]

        # Servers
        self.servers = [
            ServerEntry(
                name=s["name"],
                host=s["host"],
                port=int(s.get("port", 443)),
            )
            for s in data.get("servers", [])
            if "name" in s and "host" in s
        ]

        # Scripts
        scripts = data.get("scripts", {})
        self.scripts = ScriptsConfig(
            update_containers=str(scripts.get("update_containers", "")),
            backup=str(scripts.get("backup", "")),
        )

        # API
        api_data = data.get("api", {})
        self.api = ApiConfig(
            enabled=bool(api_data.get("enabled", False)),
            port=int(api_data.get("port", 8120)),
            api_key=str(api_data.get("api_key", "")),
        )

        # Monitoring
        mon = data.get("monitoring", {})
        mon_servers = [
            ServerEntry(name=s["name"], host=s["host"], port=int(s.get("port", 443)))
            for s in mon.get("servers", [])
            if "name" in s and "host" in s
        ]
        self.monitoring = MonitoringConfig(
            interval_minutes=int(mon.get("interval_minutes", 5)),
            containers=mon.get("containers", []),
            servers=mon_servers,
            services=mon.get("services", []),
            thresholds=mon.get("thresholds", MonitoringConfig().thresholds),
            security=mon.get("security", MonitoringConfig().security),
        )


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load and parse a YAML file with env var interpolation."""
    text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(text) or {}
    return _interpolate_env(raw)


class _ConfigReloadHandler(FileSystemEventHandler):
    """Debounced file watcher that reloads config on change."""

    def __init__(self, config_path: Path, app_config: AppConfig) -> None:
        self._config_path = config_path
        self._app_config = app_config
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def on_modified(self, event) -> None:
        if Path(event.src_path).resolve() != self._config_path.resolve():
            return
        self._schedule_reload()

    def on_created(self, event) -> None:
        if Path(event.src_path).resolve() != self._config_path.resolve():
            return
        self._schedule_reload()

    def _schedule_reload(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(_DEBOUNCE_SECONDS, self._do_reload)
            self._timer.daemon = True
            self._timer.start()

    def _do_reload(self) -> None:
        try:
            data = _load_yaml(self._config_path)
            self._app_config.update_from_dict(data)
            logger.info("Config reloaded from %s", self._config_path)
        except Exception:
            logger.exception("Failed to reload config from %s", self._config_path)


# Module-level singleton
config = AppConfig()
_observer: Observer | None = None


def load_config(path: str | Path | None = None) -> AppConfig:
    """Load config from YAML file and start the file watcher.

    Call this once at application startup. Subsequent changes to the YAML file
    are picked up automatically via watchdog.
    """
    global _observer

    config_path = Path(path) if path else _DEFAULT_CONFIG_PATH
    if not config_path.exists():
        logger.warning("Config file %s not found, using defaults", config_path)
        return config

    data = _load_yaml(config_path)
    config.update_from_dict(data)
    logger.info("Config loaded from %s", config_path)

    # Start file watcher
    if _observer is not None:
        _observer.stop()
        _observer.join(timeout=2)

    handler = _ConfigReloadHandler(config_path, config)
    _observer = Observer()
    _observer.schedule(handler, str(config_path.parent), recursive=False)
    _observer.daemon = True
    _observer.start()

    return config


def reload_config(path: str | Path | None = None) -> None:
    """Manually reload the config file."""
    config_path = Path(path) if path else _DEFAULT_CONFIG_PATH
    if not config_path.exists():
        logger.warning("Config file %s not found", config_path)
        return
    data = _load_yaml(config_path)
    config.update_from_dict(data)
    logger.info("Config manually reloaded from %s", config_path)
