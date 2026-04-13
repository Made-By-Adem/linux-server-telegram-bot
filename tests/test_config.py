"""Tests for config parsing -- MonitoredItem, backwards compat, policy lookup."""

from linux_server_bot.config import MonitoredItem, MonitoringConfig, _parse_monitored_items


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
        items = _parse_monitored_items([
            {"name": "nginx", "on_failure": "ignore"},
            {"name": "docker", "on_failure": "notify_restart"},
        ])
        assert items[0].on_failure == "ignore"
        assert items[1].on_failure == "notify_restart"

    def test_dict_without_policy_defaults_to_notify(self):
        items = _parse_monitored_items([{"name": "nginx"}])
        assert items[0].on_failure == "notify"

    def test_invalid_policy_falls_back_to_notify(self):
        items = _parse_monitored_items([{"name": "nginx", "on_failure": "explode"}])
        assert items[0].on_failure == "notify"

    def test_mixed_strings_and_dicts(self):
        items = _parse_monitored_items([
            "nginx",
            {"name": "docker", "on_failure": "ignore"},
        ])
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
        mc = MonitoringConfig(services=[
            MonitoredItem(name="nginx", on_failure="ignore"),
            MonitoredItem(name="docker", on_failure="notify_restart"),
        ])
        assert mc.get_service_policy("nginx") == "ignore"
        assert mc.get_service_policy("docker") == "notify_restart"

    def test_get_service_policy_default(self):
        mc = MonitoringConfig(services=[])
        assert mc.get_service_policy("unknown") == "notify"

    def test_get_container_policy_found(self):
        mc = MonitoringConfig(containers=[
            MonitoredItem(name="portainer", on_failure="notify_restart"),
        ])
        assert mc.get_container_policy("portainer") == "notify_restart"

    def test_get_container_policy_default(self):
        mc = MonitoringConfig()
        assert mc.get_container_policy("unknown") == "notify"
