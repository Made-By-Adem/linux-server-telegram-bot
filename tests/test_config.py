"""Tests for config parsing -- MonitoredItem, backwards compat, policy lookup, thresholds."""

import pytest

from linux_server_bot.config import (
    THRESHOLD_KEYS,
    MonitoredItem,
    MonitoringConfig,
    _parse_monitored_items,
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


class TestMonitoringConfigPolicyLookup:
    def test_get_service_policy_found(self):
        mc = MonitoringConfig(
            services=[
                MonitoredItem(name="nginx", on_failure="ignore"),
                MonitoredItem(name="docker", on_failure="notify_restart"),
            ]
        )
        assert mc.get_service_policy("nginx") == "ignore"
        assert mc.get_service_policy("docker") == "notify_restart"

    def test_get_service_policy_default(self):
        mc = MonitoringConfig(services=[])
        assert mc.get_service_policy("unknown") == "notify"

    def test_get_container_policy_found(self):
        mc = MonitoringConfig(
            containers=[
                MonitoredItem(name="portainer", on_failure="notify_restart"),
            ]
        )
        assert mc.get_container_policy("portainer") == "notify_restart"

    def test_get_container_policy_default(self):
        mc = MonitoringConfig()
        assert mc.get_container_policy("unknown") == "notify"


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
        import yaml

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"monitoring": {"thresholds": {"cpu_percent": 80}}}))
        update_monitoring_threshold("cpu_percent", 90, config_path=config_file)

        reloaded = yaml.safe_load(config_file.read_text())
        assert reloaded["monitoring"]["thresholds"]["cpu_percent"] == 90

    def test_valid_update_creates_thresholds_section(self, tmp_path):
        import yaml

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"monitoring": {}}))
        update_monitoring_threshold("storage_percent", 85, config_path=config_file)

        reloaded = yaml.safe_load(config_file.read_text())
        assert reloaded["monitoring"]["thresholds"]["storage_percent"] == 85

    def test_threshold_keys_have_valid_ranges(self):
        for key, (lo, hi) in THRESHOLD_KEYS.items():
            assert lo < hi, f"{key}: lo ({lo}) must be less than hi ({hi})"
            assert lo >= 1, f"{key}: lo must be >= 1"
