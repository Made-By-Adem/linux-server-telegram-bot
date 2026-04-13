"""API routes -- all endpoints calling into shared/actions."""

from __future__ import annotations

import logging
import os
from dataclasses import asdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from linux_server_bot.api.auth import verify_api_key
from linux_server_bot.config import (
    THRESHOLD_KEYS,
    add_monitored_item,
    config,
    reload_config,
    remove_monitored_item,
    update_monitoring_policy,
    update_monitoring_threshold,
)
from linux_server_bot.shared.actions import (
    backups,
    compose,
    docker,
    logs,
    security,
    servers,
    services,
    sysinfo,
    updates,
    wol,
)
from linux_server_bot.shared.shell import run_command, run_shell

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", dependencies=[Depends(verify_api_key)])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CommandRequest(BaseModel):
    command: str


class RebootRequest(BaseModel):
    confirm: bool = False


class ThresholdUpdateRequest(BaseModel):
    key: str
    value: int | float


class MonitoredItemRequest(BaseModel):
    name: str
    on_failure: str = "notify"


# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------


@router.get("/docker/status")
async def docker_status():
    if not os.path.exists("/var/run/docker.sock"):
        return {"success": False, "error": "Docker socket not available"}
    container_names = config.get_container_names()
    if not container_names:
        return {"success": True, "data": []}
    all_statuses = docker.get_container_statuses()
    # Filter to only configured containers
    configured = set(container_names)
    filtered = [s for s in all_statuses if s.name in configured]
    return {"success": True, "data": [asdict(s) for s in filtered]}


@router.post("/docker/{action}/{name}")
async def docker_action(action: str, name: str):
    if action not in ("start", "stop", "restart"):
        return {"success": False, "error": f"Invalid action: {action}"}
    result = docker.container_action(action, name)
    return result


@router.post("/docker/{action}")
async def docker_action_all(action: str):
    if action not in ("start_all", "stop_all", "restart_all"):
        return {"success": False, "error": f"Invalid action: {action}"}
    real_action = action.replace("_all", "")
    results = docker.container_action_all(real_action, config.get_container_names())
    return {"success": all(r["success"] for r in results), "data": results}


@router.post("/docker/cleanup")
async def docker_cleanup():
    return docker.docker_cleanup()


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


@router.get("/services/status")
async def services_status():
    service_names = config.get_service_names()
    if not service_names:
        return {"success": True, "data": []}
    statuses = services.get_service_statuses(service_names)
    return {"success": True, "data": [asdict(s) for s in statuses]}


@router.post("/services/{action}/{name}")
async def service_action(action: str, name: str):
    if action not in ("start", "stop", "restart"):
        return {"success": False, "error": f"Invalid action: {action}"}
    return services.service_action(action, name)


# ---------------------------------------------------------------------------
# Compose
# ---------------------------------------------------------------------------


def _find_stack(name: str):
    for s in config.compose_stacks:
        if s.name == name:
            return s
    return None


@router.get("/compose/status")
async def compose_status():
    results = []
    for stack in config.compose_stacks:
        results.append(compose.get_stack_status(stack))
    return {"success": True, "data": results}


@router.post("/compose/{action}/{name}")
async def compose_action(action: str, name: str):
    stack = _find_stack(name)
    if not stack:
        return {"success": False, "error": f"Stack '{name}' not found"}
    actions = {
        "up": compose.stack_up,
        "down": compose.stack_down,
        "restart": compose.stack_restart,
        "pull": compose.stack_pull_recreate,
    }
    handler = actions.get(action)
    if not handler:
        return {"success": False, "error": f"Invalid action: {action}"}
    return handler(stack)


@router.get("/compose/logs/{name}")
async def compose_logs(name: str, tail: int = 50):
    stack = _find_stack(name)
    if not stack:
        return {"success": False, "error": f"Stack '{name}' not found"}
    return compose.stack_logs(stack, tail=tail)


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------


@router.get("/logs")
async def logs_list():
    entries = logs.list_available_logs()
    return {"success": True, "data": entries}


@router.get("/logs/{index}")
async def logs_read(index: int, tail: int = 50):
    return logs.read_log_tail(index, tail=tail)


# ---------------------------------------------------------------------------
# System info
# ---------------------------------------------------------------------------


@router.get("/sysinfo")
async def sysinfo_full():
    return {"success": True, "data": sysinfo.get_sysinfo_text()}


@router.get("/sysinfo/cpu")
async def sysinfo_cpu():
    return sysinfo.get_cpu_usage()


@router.get("/sysinfo/memory")
async def sysinfo_memory():
    return sysinfo.get_memory_usage()


@router.get("/sysinfo/disk")
async def sysinfo_disk():
    return sysinfo.get_disk_usage()


@router.get("/sysinfo/temperature")
async def sysinfo_temperature():
    return sysinfo.get_temperature()


@router.post("/sysinfo/stress-test")
async def sysinfo_stress_test(minutes: int = 1):
    if not config.features.stress_test:
        return {"success": False, "error": "Stress test feature is disabled"}
    if minutes < 1 or minutes > 60:
        return {"success": False, "error": "Duration must be between 1 and 60 minutes"}
    return sysinfo.run_stress_test(minutes)


@router.post("/sysinfo/fan")
async def sysinfo_fan(state: int = 0):
    if not config.features.fan_control:
        return {"success": False, "error": "Fan control feature is disabled"}
    if state not in (0, 1):
        return {"success": False, "error": "State must be 0 (off/auto) or 1 (on)"}
    return sysinfo.set_fan_state(state)


# ---------------------------------------------------------------------------
# Monitoring Thresholds
# ---------------------------------------------------------------------------


@router.get("/monitoring/thresholds")
async def monitoring_thresholds():
    return {"success": True, "data": dict(config.monitoring.thresholds)}


@router.put("/monitoring/thresholds")
async def monitoring_thresholds_update(req: ThresholdUpdateRequest):
    if req.key not in THRESHOLD_KEYS:
        valid = ", ".join(THRESHOLD_KEYS)
        return {"success": False, "error": f"Invalid key: {req.key}. Valid keys: {valid}"}
    lo, hi = THRESHOLD_KEYS[req.key]
    if not (lo <= req.value <= hi):
        return {"success": False, "error": f"Value must be between {lo} and {hi}"}
    try:
        update_monitoring_threshold(req.key, req.value)
        return {"success": True, "data": dict(config.monitoring.thresholds)}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------


@router.get("/security")
async def security_full():
    return {"success": True, "data": security.get_full_security_status()}


@router.get("/security/fail2ban")
async def security_fail2ban():
    return security.get_fail2ban_status()


@router.get("/security/ufw")
async def security_ufw():
    return security.get_ufw_status()


@router.get("/security/ssh")
async def security_ssh():
    return security.get_ssh_sessions()


@router.get("/security/failed-logins")
async def security_failed_logins():
    return security.get_failed_logins()


@router.get("/security/updates")
async def security_updates():
    return security.get_available_updates()


# ---------------------------------------------------------------------------
# Servers
# ---------------------------------------------------------------------------


@router.get("/servers/ping")
async def servers_ping():
    results = []
    for s in config.servers:
        results.append(servers.ping_server_with_retry(s.name, s.host, s.port))
    return {"success": True, "data": results}


# ---------------------------------------------------------------------------
# WoL
# ---------------------------------------------------------------------------


@router.post("/wol")
async def wol_wake():
    if not config.wol.address:
        return {"success": False, "error": "WoL not configured"}
    return wol.wake_device(config.wol.address, config.wol.interface)


# ---------------------------------------------------------------------------
# Updates
# ---------------------------------------------------------------------------


@router.post("/updates/dry-run")
async def updates_dry_run():
    script = config.scripts.update_containers
    if not script:
        return {"success": False, "error": "Update script not configured"}
    return updates.dry_run_updates(script)


@router.post("/updates/run")
async def updates_run():
    script = config.scripts.update_containers
    if not script:
        return {"success": False, "error": "Update script not configured"}
    return updates.trigger_updates(script)


@router.post("/updates/rollback")
async def updates_rollback():
    script = config.scripts.update_containers
    if not script:
        return {"success": False, "error": "Update script not configured"}
    return updates.rollback_updates(script)


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------


@router.post("/backups/trigger")
async def backups_trigger():
    script = config.scripts.backup
    if not script:
        return {"success": False, "error": "Backup script not configured"}
    return backups.trigger_backup(script)


@router.get("/backups/status")
async def backups_status():
    return backups.get_backup_status()


@router.get("/backups/size")
async def backups_size():
    return backups.get_backup_size()


# ---------------------------------------------------------------------------
# Command execution
# ---------------------------------------------------------------------------


@router.post("/command")
async def command_exec(req: CommandRequest):
    if not req.command.strip():
        return {"success": False, "error": "Empty command"}
    result = run_shell(req.command, timeout=60)
    return {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


# ---------------------------------------------------------------------------
# Reboot
# ---------------------------------------------------------------------------


@router.post("/reboot")
async def reboot_server(req: RebootRequest):
    if not req.confirm:
        return {"success": False, "error": "Confirmation required (set confirm: true)"}
    result = run_command(["sudo", "reboot", "now"])
    return {"success": result.success, "error": result.stderr if not result.success else ""}


# ---------------------------------------------------------------------------
# Monitored Items (services & containers CRUD)
# ---------------------------------------------------------------------------


@router.get("/services/list")
async def services_list():
    return {
        "success": True,
        "data": [{"name": s.name, "on_failure": s.on_failure} for s in config.services],
    }


@router.post("/services/add")
async def services_add(req: MonitoredItemRequest):
    try:
        add_monitored_item("services", req.name, req.on_failure)
        return {"success": True, "data": {"name": req.name, "on_failure": req.on_failure}}
    except ValueError as e:
        return {"success": False, "error": str(e)}


@router.delete("/services/{name}")
async def services_remove(name: str):
    try:
        remove_monitored_item("services", name)
        return {"success": True}
    except ValueError as e:
        return {"success": False, "error": str(e)}


@router.put("/services/{name}/policy")
async def services_update_policy(name: str, req: MonitoredItemRequest):
    try:
        update_monitoring_policy("services", name, req.on_failure)
        return {"success": True, "data": {"name": name, "on_failure": req.on_failure}}
    except ValueError as e:
        return {"success": False, "error": str(e)}


@router.get("/containers/list")
async def containers_list():
    return {
        "success": True,
        "data": [{"name": c.name, "on_failure": c.on_failure} for c in config.containers],
    }


@router.post("/containers/add")
async def containers_add(req: MonitoredItemRequest):
    try:
        add_monitored_item("containers", req.name, req.on_failure)
        return {"success": True, "data": {"name": req.name, "on_failure": req.on_failure}}
    except ValueError as e:
        return {"success": False, "error": str(e)}


@router.delete("/containers/{name}")
async def containers_remove(name: str):
    try:
        remove_monitored_item("containers", name)
        return {"success": True}
    except ValueError as e:
        return {"success": False, "error": str(e)}


@router.put("/containers/{name}/policy")
async def containers_update_policy(name: str, req: MonitoredItemRequest):
    try:
        update_monitoring_policy("containers", name, req.on_failure)
        return {"success": True, "data": {"name": name, "on_failure": req.on_failure}}
    except ValueError as e:
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@router.post("/config/reload")
async def config_reload():
    try:
        reload_config()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
