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
from watchdog.observers.polling import PollingObserver

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
class MonitoredItem:
    """A service or container with a failure-action policy.

    ``on_failure`` is one of:
    - ``"notify"`` (default) -- send a Telegram alert, but do not restart.
    - ``"notify_restart"`` -- notify *and* attempt restart.
    - ``"ignore"`` -- silently skip.
    """

    name: str
    on_failure: str = "notify"

    # Allowed values (class-level constant)
    ACTIONS = ("ignore", "notify", "notify_restart")


def _parse_monitored_items(raw: list) -> list[MonitoredItem]:
    """Parse a list of strings or dicts into ``MonitoredItem`` objects.

    Accepts both formats for backwards compatibility::

        # simple (defaults to notify_restart)
        services:
          - nginx
          - docker

        # detailed
        services:
          - name: nginx
            on_failure: notify
          - name: docker
            on_failure: ignore
    """
    items: list[MonitoredItem] = []
    for entry in raw:
        if isinstance(entry, str):
            items.append(MonitoredItem(name=entry))
        elif isinstance(entry, dict) and "name" in entry:
            action = str(entry.get("on_failure", "notify"))
            if action not in MonitoredItem.ACTIONS:
                action = "notify"
            items.append(MonitoredItem(name=entry["name"], on_failure=action))
    return items


@dataclass
class MonitoringConfig:
    interval_minutes: int = 5
    servers: list[ServerEntry] = field(default_factory=list)
    thresholds: dict[str, int | float] = field(
        default_factory=lambda: {
            "cpu_percent": 80,
            "storage_percent": 90,
            "temperature_celsius": 50,
            "recheck_delay_seconds": 5,
        }
    )
    security: dict[str, bool] = field(
        default_factory=lambda: {
            "check_fail2ban": True,
            "check_ufw": True,
            "check_ssh_sessions": True,
        }
    )


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
    pironman: bool = False
    reboot: bool = True
    custom_scripts: bool = True
    settings: bool = True


@dataclass
class PironmanConfig:
    variant: str = "base"

    VARIANTS = ("base", "max")


@dataclass
class ApiConfig:
    enabled: bool = False
    port: int = 8120
    api_key: str = ""


@dataclass
class CustomScript:
    """A user-defined script that can be run from the bot menu."""

    name: str
    path: str
    timeout: int = 300


@dataclass
class BackupConfig:
    """Backup script configuration.

    ``targets`` is an optional list of arguments passed as a single positional
    parameter to the backup script. When non-empty, the bot renders one
    sub-button per target (e.g. ``Backup ac1`` runs ``<path> ac1``).
    """

    path: str = ""
    targets: list[str] = field(default_factory=list)


@dataclass
class ScriptsConfig:
    update_containers: str = ""
    backup: BackupConfig = field(default_factory=BackupConfig)
    custom: list[CustomScript] = field(default_factory=list)


@dataclass
class AppConfig:
    """Central application configuration, loaded from YAML."""

    bot_token: str = ""
    allowed_users: list[int] = field(default_factory=list)
    wol: WolConfig = field(default_factory=WolConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    services: list[MonitoredItem] = field(default_factory=list)
    containers: list[MonitoredItem] = field(default_factory=list)
    compose_stacks: list[ComposeStack] = field(default_factory=list)
    servers: list[ServerEntry] = field(default_factory=list)
    logfiles: list[str] = field(default_factory=list)
    scripts: ScriptsConfig = field(default_factory=ScriptsConfig)
    pironman: PironmanConfig = field(default_factory=PironmanConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    server_states_path: str = "server_states.json"
    log_directory: str = "./logs"

    def get_service_names(self) -> list[str]:
        """Return configured service names."""
        return [s.name for s in self.services]

    def get_container_names(self) -> list[str]:
        """Return configured container names."""
        return [c.name for c in self.containers]

    def get_service_policy(self, name: str) -> str:
        """Look up the on_failure policy for a service, default ``'notify'``."""
        for item in self.services:
            if item.name == name:
                return item.on_failure
        return "notify"

    def get_container_policy(self, name: str) -> str:
        """Look up the on_failure policy for a container, default ``'notify'``.

        Supports glob patterns: if no exact match is found, pattern entries
        (containing ``*``, ``?``, or ``[``) are checked via ``fnmatch``.
        """
        import fnmatch

        for item in self.containers:
            if item.name == name:
                return item.on_failure
        # Fallback: check glob patterns
        for item in self.containers:
            if any(c in item.name for c in ("*", "?", "[")) and fnmatch.fnmatch(name, item.name):
                return item.on_failure
        return "notify"

    def update_from_dict(self, data: dict[str, Any]) -> None:
        """Update config fields from a parsed YAML dict."""
        telegram = data.get("telegram", {})
        self.bot_token = telegram.get("bot_token", os.environ.get("SECRET_TOKEN", self.bot_token))
        raw_users = telegram.get("allowed_users", [])
        parsed_users: list[int] = []
        for u in raw_users:
            if not u:
                continue
            try:
                parsed_users.append(int(u))
            except (ValueError, TypeError):
                logger.error(
                    "Invalid chat ID '%s' in allowed_users -- must be a number. "
                    "Check your .env file: CHAT_ID_PERSON1 should contain only digits.",
                    u,
                )
        self.allowed_users = parsed_users

        wol = data.get("wol", {})
        self.wol = WolConfig(
            address=str(wol.get("address", "")),
            hostname=str(wol.get("hostname", "")),
            interface=str(wol.get("interface", "eth0")),
        )

        features = data.get("features", {})
        self.features = (
            FeaturesConfig(**{k: v for k, v in features.items() if k in FeaturesConfig.__dataclass_fields__})
            if features
            else FeaturesConfig()
        )

        self.services = _parse_monitored_items(data.get("services", []))
        self.containers = _parse_monitored_items(data.get("containers", []))
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
        custom_scripts = [
            CustomScript(name=s["name"], path=s["path"], timeout=int(s.get("timeout", 300)))
            for s in scripts.get("custom", [])
            if isinstance(s, dict) and "name" in s and "path" in s
        ]
        # Backup config accepts either a plain path string (legacy) or a dict
        # with ``path`` and optional ``targets`` list.
        raw_backup = scripts.get("backup", "")
        if isinstance(raw_backup, dict):
            backup_cfg = BackupConfig(
                path=str(raw_backup.get("path", "")),
                targets=[str(t) for t in (raw_backup.get("targets") or []) if t],
            )
        else:
            backup_cfg = BackupConfig(path=str(raw_backup))
        self.scripts = ScriptsConfig(
            update_containers=str(scripts.get("update_containers", "")),
            backup=backup_cfg,
            custom=custom_scripts,
        )

        # Pironman
        pironman_data = data.get("pironman", {})
        variant = str(pironman_data.get("variant", "base")).lower()
        if variant not in PironmanConfig.VARIANTS:
            variant = "base"
        self.pironman = PironmanConfig(variant=variant)

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
            servers=mon_servers,
            thresholds=mon.get("thresholds", MonitoringConfig().thresholds),
            security=mon.get("security", MonitoringConfig().security),
        )


def _check_pironman_availability() -> None:
    """Auto-disable pironman feature if the pironman5 CLI is not installed."""
    if not config.features.pironman:
        return
    from linux_server_bot.shared.actions.pironman import is_available

    if not is_available():
        config.features.pironman = False
        logger.warning(
            "pironman5 CLI not found -- disabling pironman feature. "
            "Install pironman5 to enable it: https://github.com/sunfounder/pironman5"
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

    def on_moved(self, event) -> None:
        # Many editors write via temp file + atomic rename.
        dest = getattr(event, "dest_path", None)
        if not dest:
            return
        if Path(dest).resolve() != self._config_path.resolve():
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
            _check_pironman_availability()
            logger.info("Config reloaded from %s", self._config_path)
        except Exception:
            logger.exception("Failed to reload config from %s", self._config_path)


# Module-level singleton
config = AppConfig()
_observer: PollingObserver | None = None


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

    _check_pironman_availability()

    # Start file watcher
    if _observer is not None:
        _observer.stop()
        _observer.join(timeout=2)

    handler = _ConfigReloadHandler(config_path, config)
    _observer = PollingObserver()
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


def update_monitoring_policy(
    kind: str,
    name: str,
    on_failure: str,
    config_path: str | Path | None = None,
) -> None:
    """Update the on_failure policy for a monitored service or container.

    Writes the change to config.yaml (the watchdog auto-reloads it) and
    updates the in-memory config immediately.

    Parameters
    ----------
    kind:
        ``"services"`` or ``"containers"``.
    name:
        Name of the service or container.
    on_failure:
        One of ``"ignore"``, ``"notify"``, ``"notify_restart"``.
    """
    if on_failure not in MonitoredItem.ACTIONS:
        raise ValueError(f"Invalid on_failure value: {on_failure!r}")

    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    # Update the raw YAML (without env interpolation, to preserve ${VAR} refs)
    raw_text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(raw_text) or {}
    items = raw.get(kind, [])

    # Find and update the item
    updated = False
    for i, entry in enumerate(items):
        entry_name = entry if isinstance(entry, str) else entry.get("name", "")
        if entry_name == name:
            items[i] = {"name": name, "on_failure": on_failure}
            updated = True
            break

    if not updated:
        items.append({"name": name, "on_failure": on_failure})

    raw[kind] = items

    path.write_text(
        yaml.dump(raw, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    logger.info("Updated %s policy for %s to %s", kind, name, on_failure)

    # Immediate in-memory update
    item_list = getattr(config, kind, [])
    for item in item_list:
        if item.name == name:
            item.on_failure = on_failure
            return
    item_list.append(MonitoredItem(name=name, on_failure=on_failure))


def update_feature(
    feature: str,
    enabled: bool,
    config_path: str | Path | None = None,
) -> None:
    """Toggle a feature on or off in config.yaml and in-memory config."""
    if feature not in FeaturesConfig.__dataclass_fields__:
        raise ValueError(f"Invalid feature: {feature!r}")

    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw_text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(raw_text) or {}
    features = raw.setdefault("features", {})
    features[feature] = enabled
    raw["features"] = features

    path.write_text(
        yaml.dump(raw, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    logger.info("Updated feature %s to %s", feature, enabled)

    # Immediate in-memory update
    setattr(config.features, feature, enabled)


# Valid threshold keys and their allowed ranges
THRESHOLD_KEYS = {
    "cpu_percent": (1, 100),
    "storage_percent": (1, 100),
    "temperature_celsius": (1, 150),
    "recheck_delay_seconds": (1, 60),
}


def update_monitoring_threshold(
    key: str,
    value: int | float,
    config_path: str | Path | None = None,
) -> None:
    """Update a monitoring threshold in config.yaml and in-memory config.

    Parameters
    ----------
    key:
        One of ``"cpu_percent"``, ``"storage_percent"``, ``"temperature_celsius"``.
    value:
        New threshold value (must be within the valid range for the key).
    """
    if key not in THRESHOLD_KEYS:
        raise ValueError(f"Invalid threshold key: {key!r}")

    lo, hi = THRESHOLD_KEYS[key]
    if not (lo <= value <= hi):
        raise ValueError(f"{key} must be between {lo} and {hi}")

    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw_text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(raw_text) or {}
    mon = raw.setdefault("monitoring", {})
    thresholds = mon.setdefault("thresholds", {})
    thresholds[key] = value
    raw["monitoring"] = mon

    path.write_text(
        yaml.dump(raw, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    logger.info("Updated threshold %s to %s", key, value)

    # Immediate in-memory update
    config.monitoring.thresholds[key] = value


def add_monitored_item(
    kind: str,
    name: str,
    on_failure: str = "notify",
    config_path: str | Path | None = None,
) -> None:
    """Add a service or container to the config.

    Parameters
    ----------
    kind:
        ``"services"`` or ``"containers"``.
    name:
        Name of the service or container.
    on_failure:
        One of ``"ignore"``, ``"notify"``, ``"notify_restart"``.
    """
    if kind not in ("services", "containers"):
        raise ValueError(f"Invalid kind: {kind!r}")
    if on_failure not in MonitoredItem.ACTIONS:
        raise ValueError(f"Invalid on_failure value: {on_failure!r}")

    # Check if already exists
    item_list: list[MonitoredItem] = getattr(config, kind, [])
    for item in item_list:
        if item.name == name:
            raise ValueError(f"{kind[:-1].capitalize()} '{name}' already exists")

    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw_text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(raw_text) or {}
    items = raw.get(kind, [])
    items.append({"name": name, "on_failure": on_failure})
    raw[kind] = items

    path.write_text(
        yaml.dump(raw, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    logger.info("Added %s '%s' with policy %s", kind[:-1], name, on_failure)

    # Immediate in-memory update
    item_list.append(MonitoredItem(name=name, on_failure=on_failure))


def remove_monitored_item(
    kind: str,
    name: str,
    config_path: str | Path | None = None,
) -> None:
    """Remove a service or container from the config.

    Parameters
    ----------
    kind:
        ``"services"`` or ``"containers"``.
    name:
        Name of the service or container to remove.
    """
    if kind not in ("services", "containers"):
        raise ValueError(f"Invalid kind: {kind!r}")

    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    if not path.exists():
        logger.warning("Config file %s not found, cannot remove item", path)
        return

    raw_text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(raw_text) or {}
    items = raw.get(kind, [])

    new_items = []
    for entry in items:
        entry_name = entry if isinstance(entry, str) else entry.get("name", "")
        if entry_name != name:
            new_items.append(entry)

    if len(new_items) == len(items):
        raise ValueError(f"{kind[:-1].capitalize()} '{name}' not found")

    raw[kind] = new_items

    path.write_text(
        yaml.dump(raw, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    logger.info("Removed %s '%s'", kind[:-1], name)

    # Immediate in-memory update
    item_list: list[MonitoredItem] = getattr(config, kind, [])
    config.__dict__[kind] = [i for i in item_list if i.name != name]
