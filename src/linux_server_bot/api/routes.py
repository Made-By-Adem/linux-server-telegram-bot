"""API routes -- all endpoints calling into shared/actions."""

from __future__ import annotations

import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from linux_server_bot.api.auth import verify_api_key
from linux_server_bot.config import config, reload_config
from linux_server_bot.shared.actions import (
    backups,
    compose,
    docker,
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


# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------


@router.get("/docker/status")
async def docker_status():
    statuses = docker.get_container_statuses()
    return {"success": True, "data": [asdict(s) for s in statuses]}


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
    results = docker.container_action_all(real_action)
    return {"success": all(r["success"] for r in results), "data": results}


@router.post("/docker/cleanup")
async def docker_cleanup():
    return docker.docker_cleanup()


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


@router.get("/services/status")
async def services_status():
    statuses = services.get_service_statuses(config.services)
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
# Config
# ---------------------------------------------------------------------------


@router.post("/config/reload")
async def config_reload():
    try:
        reload_config()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
