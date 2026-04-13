# Linux Server Management API

You manage Linux servers via a REST API. Each server runs the Linux Server Bot API (port auto-detected on startup, default 8120), optionally exposed via Cloudflare Tunnel.

## Authentication

Every request (except health check) requires the `X-API-Key` header. The API key is auto-generated on first startup (check `.env` on the server).

```
X-API-Key: <api-key>
```

## Base URL

```
https://<server-hostname>/api   # via Cloudflare Tunnel
http://localhost:<port>/api     # local (default 8120, auto-detected if busy)
```

## Response Format

All endpoints return JSON with a `success` boolean:

```json
{"success": true, "data": ...}
{"success": false, "error": "description"}
```

## Endpoints

### Health & Config

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (no auth) |
| POST | `/api/config/reload` | Hot-reload config.yaml |

### Docker Containers

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/docker/status` | List all containers with status |
| POST | `/api/docker/start/{name}` | Start container |
| POST | `/api/docker/stop/{name}` | Stop container |
| POST | `/api/docker/restart/{name}` | Restart container |
| POST | `/api/docker/start_all` | Start all containers |
| POST | `/api/docker/stop_all` | Stop all containers |
| POST | `/api/docker/restart_all` | Restart all containers |
| POST | `/api/docker/cleanup` | Docker system prune |

### Docker Compose Stacks

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/compose/status` | All stack statuses |
| POST | `/api/compose/up/{name}` | Start stack |
| POST | `/api/compose/down/{name}` | Stop stack |
| POST | `/api/compose/restart/{name}` | Restart stack |
| POST | `/api/compose/pull/{name}` | Pull images & recreate |
| GET | `/api/compose/logs/{name}?tail=50` | View stack logs |

### Systemd Services

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/services/status` | All service statuses |
| POST | `/api/services/start/{name}` | Start service |
| POST | `/api/services/stop/{name}` | Stop service |
| POST | `/api/services/restart/{name}` | Restart service |

### Log Files

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/logs` | List available log files with index |
| GET | `/api/logs/{index}?tail=50` | Read last N lines of a log file |

### System Info

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/sysinfo` | Full system overview (text) |
| GET | `/api/sysinfo/cpu` | CPU usage % |
| GET | `/api/sysinfo/memory` | Memory: total, used, free, cache |
| GET | `/api/sysinfo/disk` | Disk usage per partition |
| GET | `/api/sysinfo/temperature` | CPU temperature |
| POST | `/api/sysinfo/stress-test?minutes=1` | Run CPU stress test (feature-flag gated) |
| POST | `/api/sysinfo/fan?state=0` | Set fan state: 0=off/auto, 1=on (feature-flag gated) |

### Monitoring Thresholds

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/monitoring/thresholds` | Get current thresholds (cpu_percent, storage_percent, temperature_celsius) |
| PUT | `/api/monitoring/thresholds` | Update a threshold (body: `{"key": "cpu_percent", "value": 85}`) |

### Security

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/security` | Full security overview |
| GET | `/api/security/fail2ban` | Fail2ban jail status & bans |
| GET | `/api/security/ufw` | UFW firewall rules & status |
| GET | `/api/security/ssh` | Active SSH sessions |
| GET | `/api/security/failed-logins` | Recent failed login attempts |
| GET | `/api/security/updates` | Available system updates |

### Server Ping

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/servers/ping` | Ping all configured servers |

### Wake-on-LAN

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/wol` | Wake configured device |

### Container Updates (via script)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/updates/dry-run` | Preview available updates |
| POST | `/api/updates/run` | Apply container updates |
| POST | `/api/updates/rollback` | Rollback last update |

### Backups (via script)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/backups/trigger` | Start backup |
| GET | `/api/backups/status` | Backup status |
| GET | `/api/backups/size` | Backup disk usage |

### Shell Command

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/api/command` | `{"command": "..."}` | Execute shell command (60s timeout) |

### Reboot

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/api/reboot` | `{"confirm": true}` | Reboot the server |

## Error Handling

| HTTP Code | Meaning |
|-----------|---------|
| 200 | Success (check `success` field) |
| 403 | Invalid API key |
| 503 | API disabled or not configured |
| 422 | Invalid request body |

## Important Notes

- **Container names** come from Docker directly (auto-detected); **service names** from systemd enabled services (auto-detected)
- **Updates and backups** require external scripts to be installed (from [linux-server-management-scripts](https://github.com/Made-By-Adem/linux-server-management-scripts))
- **Reboot** requires explicit `{"confirm": true}` -- will not execute without it
- **Command execution** runs with server-level privileges -- use with caution
- **Config reload** picks up changes to config.yaml without restarting services
