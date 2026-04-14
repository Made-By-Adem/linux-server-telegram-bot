"""Tests for config parsing -- MonitoredItem, backwards compat, policy lookup, thresholds, CRUD."""

import pytest
import yaml

from linux_server_bot.config import (
    THRESHOLD_KEYS,
    AppConfig,
    MonitoredItem,
    _parse_monitored_items,
    add_monitored_item,
    remove_monitored_item,
    update_monitoring_policy,
    update_monitoring_threshold,
)


class TestMonitoredItem:
    def test_default_policy_is_notify(self):
        item = MonitoredItem(name="nginx")
        assert item.on_failure == "notify"

    def test_custom_policy(self):
        item = MonitoredItem(name="nginx", on_failure="notify_restart")
        assert item.on_failure == "notify_restart"


class TestParseMonitoredItems:
    def test_plain_strings_default_to_notify(self):
        items = _parse_monitored_items(["nginx", "docker"])
        assert len(items) == 2
        assert items[0].name == "nginx"
        assert items[0].on_failure == "notify"
        assert items[1].name == "docker"

    def test_dict_with_policy(self):
        items = _parse_monitored_items(
            [
                {"name": "nginx", "on_failure": "ignore"},
                {"name": "docker", "on_failure": "notify_restart"},
            ]
        )
        assert items[0].on_failure == "ignore"
        assert items[1].on_failure == "notify_restart"

    def test_dict_without_policy_defaults_to_notify(self):
        items = _parse_monitored_items([{"name": "nginx"}])
        assert items[0].on_failure == "notify"

    def test_invalid_policy_falls_back_to_notify(self):
        items = _parse_monitored_items([{"name": "nginx", "on_failure": "explode"}])
        assert items[0].on_failure == "notify"

    def test_mixed_strings_and_dicts(self):
        items = _parse_monitored_items(
            [
                "nginx",
                {"name": "docker", "on_failure": "ignore"},
            ]
        )
        assert len(items) == 2
        assert items[0].name == "nginx"
        assert items[0].on_failure == "notify"
        assert items[1].name == "docker"
        assert items[1].on_failure == "ignore"

    def test_empty_list(self):
        assert _parse_monitored_items([]) == []

    def test_skips_invalid_entries(self):
        items = _parse_monitored_items([42, None, {"no_name": True}])
        assert items == []


class TestAppConfigPolicyLookup:
    def test_get_service_policy_found(self):
        cfg = AppConfig(
            services=[
                MonitoredItem(name="nginx", on_failure="ignore"),
                MonitoredItem(name="docker", on_failure="notify_restart"),
            ]
        )
        assert cfg.get_service_policy("nginx") == "ignore"
        assert cfg.get_service_policy("docker") == "notify_restart"

    def test_get_service_policy_default(self):
        cfg = AppConfig(services=[])
        assert cfg.get_service_policy("unknown") == "notify"

    def test_get_container_policy_found(self):
        cfg = AppConfig(
            containers=[
                MonitoredItem(name="portainer", on_failure="notify_restart"),
            ]
        )
        assert cfg.get_container_policy("portainer") == "notify_restart"

    def test_get_container_policy_default(self):
        cfg = AppConfig()
        assert cfg.get_container_policy("unknown") == "notify"

    def test_get_service_names(self):
        cfg = AppConfig(
            services=[
                MonitoredItem(name="nginx"),
                MonitoredItem(name="docker"),
            ]
        )
        assert cfg.get_service_names() == ["nginx", "docker"]

    def test_get_container_names(self):
        cfg = AppConfig(
            containers=[
                MonitoredItem(name="portainer"),
                MonitoredItem(name="redis"),
            ]
        )
        assert cfg.get_container_names() == ["portainer", "redis"]


class TestUpdateMonitoringThreshold:
    def test_invalid_key_raises(self):
        with pytest.raises(ValueError, match="Invalid threshold key"):
            update_monitoring_threshold("bogus_key", 50)

    def test_value_below_range_raises(self):
        with pytest.raises(ValueError, match="must be between"):
            update_monitoring_threshold("cpu_percent", 0)

    def test_value_above_range_raises(self):
        with pytest.raises(ValueError, match="must be between"):
            update_monitoring_threshold("cpu_percent", 101)

    def test_valid_update_writes_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"monitoring": {"thresholds": {"cpu_percent": 80}}}))
        update_monitoring_threshold("cpu_percent", 90, config_path=config_file)

        reloaded = yaml.safe_load(config_file.read_text())
        assert reloaded["monitoring"]["thresholds"]["cpu_percent"] == 90

    def test_valid_update_creates_thresholds_section(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"monitoring": {}}))
        update_monitoring_threshold("storage_percent", 85, config_path=config_file)

        reloaded = yaml.safe_load(config_file.read_text())
        assert reloaded["monitoring"]["thresholds"]["storage_percent"] == 85

    def test_threshold_keys_have_valid_ranges(self):
        for key, (lo, hi) in THRESHOLD_KEYS.items():
            assert lo < hi, f"{key}: lo ({lo}) must be less than hi ({hi})"
            assert lo >= 1, f"{key}: lo must be >= 1"


class TestUpdateMonitoringPolicy:
    def test_updates_existing_item_in_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"services": [{"name": "nginx", "on_failure": "notify"}]}))
        update_monitoring_policy("services", "nginx", "ignore", config_path=config_file)

        reloaded = yaml.safe_load(config_file.read_text())
        assert reloaded["services"][0]["on_failure"] == "ignore"

    def test_adds_new_item_if_not_found(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"services": []}))
        update_monitoring_policy("services", "docker", "notify_restart", config_path=config_file)

        reloaded = yaml.safe_load(config_file.read_text())
        assert len(reloaded["services"]) == 1
        assert reloaded["services"][0]["name"] == "docker"
        assert reloaded["services"][0]["on_failure"] == "notify_restart"


class TestAddRemoveMonitoredItem:
    def test_add_service_writes_to_yaml(self, tmp_path):
        from linux_server_bot.config import config

        config.services = []  # ensure clean state
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"services": []}))
        add_monitored_item("services", "nginx", "notify", config_path=config_file)

        reloaded = yaml.safe_load(config_file.read_text())
        assert len(reloaded["services"]) == 1
        assert reloaded["services"][0]["name"] == "nginx"
        config.services = []  # cleanup

    def test_add_duplicate_raises(self, tmp_path):
        from linux_server_bot.config import config

        config.services = [MonitoredItem(name="nginx")]
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"services": [{"name": "nginx", "on_failure": "notify"}]}))

        with pytest.raises(ValueError, match="already exists"):
            add_monitored_item("services", "nginx", config_path=config_file)
        config.services = []  # cleanup

    def test_remove_service_from_yaml(self, tmp_path):
        from linux_server_bot.config import config

        config.services = [MonitoredItem(name="nginx"), MonitoredItem(name="docker")]
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "services": [
                        {"name": "nginx", "on_failure": "notify"},
                        {"name": "docker", "on_failure": "notify"},
                    ]
                }
            )
        )
        remove_monitored_item("services", "nginx", config_path=config_file)

        reloaded = yaml.safe_load(config_file.read_text())
        assert len(reloaded["services"]) == 1
        assert reloaded["services"][0]["name"] == "docker"
        config.services = []  # cleanup

    def test_remove_nonexistent_raises(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"services": []}))
        with pytest.raises(ValueError, match="not found"):
            remove_monitored_item("services", "nonexistent", config_path=config_file)

    def test_invalid_kind_raises(self):
        with pytest.raises(ValueError, match="Invalid kind"):
            add_monitored_item("invalid", "test")

    def test_add_container_writes_to_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"containers": []}))
        add_monitored_item("containers", "redis", "notify_restart", config_path=config_file)

        reloaded = yaml.safe_load(config_file.read_text())
        assert len(reloaded["containers"]) == 1
        assert reloaded["containers"][0]["name"] == "redis"
        assert reloaded["containers"][0]["on_failure"] == "notify_restart"
