# API Endpoint Reference

Complete request/response reference for every endpoint. Base URL: `http://localhost:<port>` (default 8120, auto-detected if busy) or your Cloudflare Tunnel hostname.

Authentication: `X-API-Key: <key>` header on all endpoints except `/api/health`. The API key is auto-generated on first startup (check `.env` on the server).

---

## Health

### `GET /api/health`

No authentication required.

```bash
curl -s http://localhost:8120/api/health
```

```json
{"status": "healthy", "version": "2.0.0"}
```

---

## Docker Containers

### `GET /api/docker/status`

List all containers with their status.

```bash
curl -s -H "X-API-Key: $KEY" $URL/docker/status
```

```json
{
  "success": true,
  "data": [
    {"name": "nginx", "status": "Up 3 hours", "running": true},
    {"name": "portainer", "status": "Exited (1) 2 hours ago", "running": false}
  ]
}
```

### `POST /api/docker/{action}/{name}`

Action on a single container. `action`: `start`, `stop`, or `restart`.

```bash
curl -s -X POST -H "X-API-Key: $KEY" $URL/docker/restart/nginx
```

```json
{"name": "nginx", "action": "restart", "success": true, "output": "nginx\n", "error": ""}
```

### `POST /api/docker/{action}`

Bulk action on all containers. `action`: `start_all`, `stop_all`, or `restart_all`.

```bash
curl -s -X POST -H "X-API-Key: $KEY" $URL/docker/restart_all
```

```json
{
  "success": true,
  "data": [
    {"name": "nginx", "action": "restart", "success": true, "output": "nginx\n", "error": ""},
    {"name": "portainer", "action": "restart", "success": true, "output": "portainer\n", "error": ""}
  ]
}
```

### `POST /api/docker/cleanup`

Docker system prune (removes unused images, containers, networks).

```bash
curl -s -X POST -H "X-API-Key: $KEY" $URL/docker/cleanup
```

```json
{"success": true, "output": "Deleted Images:\n...", "error": ""}
```

---

## Log Files

### `GET /api/logs`

List all configured log files with their index.

```bash
curl -s -H "X-API-Key: $KEY" $URL/logs
```

```json
{
  "success": true,
  "data": [
    {"index": 0, "path": "/var/log/auth.log", "name": "auth.log", "size_bytes": 524288},
    {"index": 1, "path": "/var/log/fail2ban.log", "name": "fail2ban.log", "size_bytes": 102400}
  ]
}
```

### `GET /api/logs/{index}?tail=50`

Read the last N lines of a log file. The `index` comes from `/api/logs`.

```bash
curl -s -H "X-API-Key: $KEY" "$URL/logs/0?tail=20"
```

```json
{
  "success": true,
  "path": "/var/log/auth.log",
  "name": "auth.log",
  "total_lines": 1500,
  "lines_returned": 20,
  "content": "Apr 13 10:30:01 server sshd[1234]: ..."
}
```

---

## Systemd Services

### `GET /api/services/status`

```bash
curl -s -H "X-API-Key: $KEY" $URL/services/status
```

```json
{
  "success": true,
  "data": [
    {"name": "nginx", "state": "active", "active": true},
    {"name": "docker", "state": "active", "active": true}
  ]
}
```

### `POST /api/services/{action}/{name}`

`action`: `start`, `stop`, or `restart`.

```bash
curl -s -X POST -H "X-API-Key: $KEY" $URL/services/restart/nginx
```

```json
{"name": "nginx", "action": "restart", "success": true, "output": "", "error": ""}
```

---

## Docker Compose Stacks

### `GET /api/compose/status`

```bash
curl -s -H "X-API-Key: $KEY" $URL/compose/status
```

```json
{
  "success": true,
  "data": [
    {"name": "media-stack", "path": "/opt/stacks/media", "success": true, "output": "NAME\tSTATUS\n..."}
  ]
}
```

### `POST /api/compose/{action}/{name}`

`action`: `up`, `down`, `restart`, or `pull` (pull also recreates containers).

```bash
curl -s -X POST -H "X-API-Key: $KEY" $URL/compose/restart/media-stack
```

```json
{"name": "media-stack", "success": true, "output": "...", "error": ""}
```

Error when stack not found:

```json
{"success": false, "error": "Stack 'unknown' not found"}
```

### `GET /api/compose/logs/{name}?tail=50`

Query parameter `tail` (default: 50) controls number of log lines.

```bash
curl -s -H "X-API-Key: $KEY" "$URL/compose/logs/media-stack?tail=100"
```

```json
{"name": "media-stack", "output": "...log lines..."}
```

---

## System Info

### `GET /api/sysinfo`

Full system overview as formatted text.

```bash
curl -s -H "X-API-Key: $KEY" $URL/sysinfo
```

```json
{"success": true, "data": "CPU: 12%\nMemory: 1.2G/4G\nDisk: 45%\n..."}
```

### `GET /api/sysinfo/cpu`

```json
{"cpu_percent": 12.5, "success": true}
```

### `GET /api/sysinfo/memory`

```json
{"total_mb": 4096, "used_mb": 1200, "free_mb": 2400, "cache_mb": 496, "success": true}
```

### `GET /api/sysinfo/disk`

```json
{
  "partitions": [
    {"device": "/dev/sda1", "total": "50G", "used": "22G", "free": "28G", "percent": "44%"}
  ],
  "success": true
}
```

### `GET /api/sysinfo/temperature`

```json
{"temperature_celsius": 42.0, "success": true}
```

### `POST /api/sysinfo/stress-test?minutes=1`

Run a CPU stress test. Requires `features.stress_test: true` in config.yaml. Duration: 1--60 minutes.

```bash
curl -s -X POST -H "X-API-Key: $KEY" "$URL/sysinfo/stress-test?minutes=2"
```

```json
{"minutes": 2, "success": true, "output": "stress-ng: info: ..."}
```

Feature disabled:

```json
{"success": false, "error": "Stress test feature is disabled"}
```

### `POST /api/sysinfo/fan?state=0`

Set fan state. Requires `features.fan_control: true` in config.yaml (typically Raspberry Pi only). `0` = off/auto, `1` = on.

```bash
curl -s -X POST -H "X-API-Key: $KEY" "$URL/sysinfo/fan?state=1"
```

```json
{"state": 1, "success": true, "error": ""}
```

---

## Monitoring Thresholds

### `GET /api/monitoring/thresholds`

Get current monitoring thresholds.

```bash
curl -s -H "X-API-Key: $KEY" $URL/monitoring/thresholds
```

```json
{
  "success": true,
  "data": {
    "cpu_percent": 80,
    "storage_percent": 90,
    "temperature_celsius": 50
  }
}
```

### `PUT /api/monitoring/thresholds`

Update a single threshold. Valid keys: `cpu_percent` (1-100), `storage_percent` (1-100), `temperature_celsius` (1-150).

```bash
curl -s -X PUT -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  $URL/monitoring/thresholds -d '{"key": "cpu_percent", "value": 85}'
```

```json
{
  "success": true,
  "data": {
    "cpu_percent": 85,
    "storage_percent": 90,
    "temperature_celsius": 50
  }
}
```

Invalid key:

```json
{"success": false, "error": "Invalid key: bogus. Valid keys: cpu_percent, storage_percent, temperature_celsius"}
```

Value out of range:

```json
{"success": false, "error": "Value must be between 1 and 100"}
```

---

## Security

### `GET /api/security`

Full security overview (aggregates all security endpoints).

```json
{
  "success": true,
  "data": {
    "fail2ban": {"available": true, "status": "Status\n...", "sshd_jail": "..."},
    "ufw": {"available": true, "status": "Status: active\n..."},
    "ssh": {"current_sessions": "...", "recent_logins": "..."},
    "failed_logins": {"output": "...", "found": true},
    "updates": {"output": "...", "up_to_date": false}
  }
}
```

### `GET /api/security/fail2ban`

```json
{"available": true, "status": "Status\n|- Number of jails: 1\n`- Jail list: sshd", "sshd_jail": "..."}
```

### `GET /api/security/ufw`

```json
{"available": true, "status": "Status: active\nTo\tAction\tFrom\n22/tcp\tALLOW\tAnywhere"}
```

### `GET /api/security/ssh`

```json
{"current_sessions": "user  pts/0  2024-01-15 10:30 (192.168.1.5)", "recent_logins": "..."}
```

### `GET /api/security/failed-logins`

```json
{"output": "Jan 15 10:30:00 server sshd[1234]: Failed password for...", "found": true}
```

### `GET /api/security/updates`

```json
{"output": "5 packages can be upgraded.", "up_to_date": false}
```

---

## Server Ping

### `GET /api/servers/ping`

Pings all configured servers (uses netcat with retry).

```bash
curl -s -H "X-API-Key: $KEY" $URL/servers/ping
```

```json
{
  "success": true,
  "data": [
    {"name": "My VPS", "host": "1.2.3.4", "port": 443, "status": "online"},
    {"name": "Web Server", "host": "5.6.7.8", "port": 80, "status": "offline"}
  ]
}
```

---

## Wake-on-LAN

### `POST /api/wol`

Sends a Wake-on-LAN magic packet to the configured device.

```bash
curl -s -X POST -H "X-API-Key: $KEY" $URL/wol
```

```json
{"success": true, "error": ""}
```

Error when not configured:

```json
{"success": false, "error": "WoL not configured"}
```

---

## Container Updates

Requires `scripts.update_containers` to be configured in config.yaml (path to [update-containers.sh](https://github.com/Made-By-Adem/linux-server-management-scripts)).

### `POST /api/updates/dry-run`

Preview what would be updated.

```json
{"success": true, "output": "Checking nginx... update available\nChecking portainer... up to date"}
```

### `POST /api/updates/run`

Execute the update.

```json
{"success": true, "output": "Updating nginx... done\n..."}
```

### `POST /api/updates/rollback`

Rollback the last update.

```json
{"success": true, "output": "Rolling back nginx... done"}
```

Error when script not configured:

```json
{"success": false, "error": "Update script not configured"}
```

---

## Backups

Requires `scripts.backup` to be configured in config.yaml (path to [backup.sh](https://github.com/Made-By-Adem/linux-server-management-scripts)).

### `POST /api/backups/trigger`

```json
{"success": true, "output": "Backup started...\nSyncing /opt/docker/... done"}
```

### `GET /api/backups/status`

```json
{"output": "Last backup: 2024-01-15 03:00 - Success"}
```

### `GET /api/backups/size`

```json
{"output": "Backup size: 12G"}
```

---

## Shell Command

### `POST /api/command`

Execute an arbitrary shell command. Timeout: 60 seconds.

```bash
curl -s -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  $URL/command -d '{"command": "df -h /"}'
```

```json
{"success": true, "stdout": "Filesystem  Size  Used  Avail  Use%  Mounted on\n/dev/sda1  50G  22G  28G  44%  /\n", "stderr": ""}
```

---

## Reboot

### `POST /api/reboot`

Requires explicit confirmation.

```bash
curl -s -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  $URL/reboot -d '{"confirm": true}'
```

```json
{"success": true, "error": ""}
```

Without confirmation:

```json
{"success": false, "error": "Confirmation required (set confirm: true)"}
```

---

## Monitored Items (Services & Containers CRUD)

### `GET /api/services/list`

List all configured services with their monitoring policy.

```bash
curl -s -H "X-API-Key: $KEY" $URL/services/list
```

```json
{
  "success": true,
  "data": [
    {"name": "nginx", "on_failure": "notify"},
    {"name": "docker", "on_failure": "notify"}
  ]
}
```

### `POST /api/services/add`

Add a new service to monitor.

```bash
curl -s -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  $URL/services/add -d '{"name": "ufw", "on_failure": "notify"}'
```

```json
{"success": true, "data": {"name": "ufw", "on_failure": "notify"}}
```

### `DELETE /api/services/{name}`

Remove a service from monitoring.

```bash
curl -s -X DELETE -H "X-API-Key: $KEY" $URL/services/nginx
```

```json
{"success": true}
```

### `PUT /api/services/{name}/policy`

Update the monitoring policy for a service.

```bash
curl -s -X PUT -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  $URL/services/nginx/policy -d '{"name": "nginx", "on_failure": "notify_restart"}'
```

```json
{"success": true, "data": {"name": "nginx", "on_failure": "notify_restart"}}
```

### `GET /api/containers/list`

List all configured containers with their monitoring policy.

```bash
curl -s -H "X-API-Key: $KEY" $URL/containers/list
```

```json
{
  "success": true,
  "data": [
    {"name": "portainer", "on_failure": "notify"},
    {"name": "nginx", "on_failure": "notify_restart"}
  ]
}
```

### `POST /api/containers/add`

Add a new container to monitor.

```bash
curl -s -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  $URL/containers/add -d '{"name": "redis", "on_failure": "notify_restart"}'
```

```json
{"success": true, "data": {"name": "redis", "on_failure": "notify_restart"}}
```

### `DELETE /api/containers/{name}`

Remove a container from monitoring.

```bash
curl -s -X DELETE -H "X-API-Key: $KEY" $URL/containers/portainer
```

```json
{"success": true}
```

### `PUT /api/containers/{name}/policy`

Update the monitoring policy for a container.

```bash
curl -s -X PUT -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  $URL/containers/portainer/policy -d '{"name": "portainer", "on_failure": "ignore"}'
```

```json
{"success": true, "data": {"name": "portainer", "on_failure": "ignore"}}
```

---

## Config Reload

### `POST /api/config/reload`

Hot-reload config.yaml without restarting services.

```bash
curl -s -X POST -H "X-API-Key: $KEY" $URL/config/reload
```

```json
{"success": true}
```

---

## Error Responses

### HTTP 403 -- Invalid API Key

```json
{"detail": "Invalid API key"}
```

### HTTP 503 -- API Disabled

```json
{"detail": "API disabled"}
```

### HTTP 503 -- API Key Not Configured

```json
{"detail": "API key not configured"}
```

### HTTP 422 -- Validation Error

```json
{"detail": [{"loc": ["body", "command"], "msg": "field required", "type": "value_error.missing"}]}
```
