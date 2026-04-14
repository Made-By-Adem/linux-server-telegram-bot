"""Tests for docker/service runtime detection robustness."""

from linux_server_bot.shared.actions import docker as docker_actions
from linux_server_bot.shared.actions import services as service_actions
from linux_server_bot.shared.shell import ShellResult


def test_docker_read_retries_with_sudo_on_socket_permission_denied(monkeypatch):
    calls = []

    def fake_run_command(cmd, timeout=30, check=False):
        calls.append(cmd)
        if cmd[0] == "docker":
            return ShellResult(
                "",
                "Got permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock",
                1,
            )
        return ShellResult("web\napi\n", "", 0)

    monkeypatch.setattr(docker_actions, "run_command", fake_run_command)

    names = docker_actions.get_container_names()

    assert names == ["web", "api"]
    assert calls[0] == ["docker", "ps", "-a", "--format", "{{.Names}}"]
    assert calls[1] == ["sudo", "docker", "ps", "-a", "--format", "{{.Names}}"]


def test_get_service_status_retries_with_service_suffix(monkeypatch):
    calls = []

    def fake_run_command(cmd, timeout=30, check=False):
        calls.append(cmd)
        if cmd[-1] == "nginx":
            return ShellResult("", "", 3)
        if cmd[-1] == "nginx.service":
            return ShellResult("active\n", "", 0)
        return ShellResult("", "", 3)

    monkeypatch.setattr(service_actions, "run_command", fake_run_command)

    status = service_actions.get_service_status("nginx")

    assert status.name == "nginx"
    assert status.active is True
    assert status.state == "active"
    assert calls == [
        ["systemctl", "is-active", "nginx"],
        ["systemctl", "is-active", "nginx.service"],
    ]


def test_get_service_statuses_normalizes_and_deduplicates(monkeypatch):
    monkeypatch.setattr(
        service_actions,
        "get_service_status",
        lambda name: service_actions.ServiceStatus(name=name, state="active", active=True),
    )

    statuses = service_actions.get_service_statuses(["nginx", "nginx.service"])
    assert len(statuses) == 1
    assert statuses[0].name == "nginx"
