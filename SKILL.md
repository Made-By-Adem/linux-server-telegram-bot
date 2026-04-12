# SKILL: Linux Server Bot

## Description
Telegram bot for managing Docker containers, Compose stacks, systemd services,
and monitoring Linux server health. Integrates with management scripts for
container updates and remote backups.

## Capabilities

### Interactive Commands
| Command | Description | Parameters |
|---------|-------------|------------|
| /menu | Show interactive menu | none |
| /docker | Docker container management | none |
| /services | Systemd service management | none |
| /ping | Ping configured servers | none |
| /sysinfo | System CPU/memory/disk/temp | none |
| /logs | View configured log files | none |
| /command | Execute shell command | interactive |
| /wakewol | Wake on LAN device | none |
| /reboot | Reboot host server | confirmation |
| /reload | Reload config without restart | none |

### New Features (v2)
| Feature | Description |
|---------|-------------|
| Docker Compose | Stack up/down/restart/pull/logs |
| Security overview | Fail2ban, UFW, SSH sessions, failed logins |
| Container updates | Trigger update script with dry-run and rollback |
| Backups | Trigger backup, view status and disk usage |
| Hot-reload | Edit config.yaml without restart |
| Feature flags | Toggle features on/off via config |

### Automated Monitoring
- Container health + auto-restart
- Service health + auto-restart
- Server/website reachability
- CPU, temperature, storage thresholds
- Failed SSH login detection
- Fail2ban ban notifications

### HTTP API (v2)
REST API for multi-server management and AI agent access. All endpoints
require `X-API-Key` header (except `/api/health`).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check (no auth) |
| `/api/docker/status` | GET | All container statuses |
| `/api/docker/{action}/{name}` | POST | Start/stop/restart container |
| `/api/docker/cleanup` | POST | Docker system prune |
| `/api/services/status` | GET | All service statuses |
| `/api/services/{action}/{name}` | POST | Start/stop/restart service |
| `/api/compose/status` | GET | All stack statuses |
| `/api/compose/{action}/{name}` | POST | Up/down/restart/pull stack |
| `/api/compose/logs/{name}` | GET | Stack logs (query: tail) |
| `/api/sysinfo` | GET | Full system info |
| `/api/sysinfo/cpu` | GET | CPU usage |
| `/api/sysinfo/memory` | GET | Memory usage |
| `/api/sysinfo/disk` | GET | Disk usage |
| `/api/sysinfo/temperature` | GET | Temperature |
| `/api/security` | GET | Full security overview |
| `/api/security/fail2ban` | GET | Fail2ban status |
| `/api/security/ufw` | GET | UFW status |
| `/api/security/ssh` | GET | SSH sessions |
| `/api/security/failed-logins` | GET | Failed login attempts |
| `/api/security/updates` | GET | Available updates |
| `/api/servers/ping` | GET | Ping all configured servers |
| `/api/wol` | POST | Send Wake-on-LAN packet |
| `/api/updates/dry-run` | POST | Dry-run container updates |
| `/api/updates/run` | POST | Run container updates |
| `/api/updates/rollback` | POST | Rollback container updates |
| `/api/backups/trigger` | POST | Trigger backup |
| `/api/backups/status` | GET | Backup status |
| `/api/backups/size` | GET | Backup disk usage |
| `/api/command` | POST | Execute shell command (body: `{"command": "..."}`) |
| `/api/reboot` | POST | Reboot server (body: `{"confirm": true}`) |
| `/api/config/reload` | POST | Reload config.yaml |

**Authentication**: `X-API-Key` header matching the `API_KEY` env variable.

**Auto-docs**: Swagger UI at `/docs`, ReDoc at `/redoc`, OpenAPI JSON at `/openapi.json`.

## Interaction Model

### Telegram Bot
- Protocol: Telegram Bot API (polling mode)
- Navigation: Persistent ReplyKeyboard (main menu) + InlineKeyboard (actions)
- Auth: User must be in allowed_users list in config.yaml
- Responses: Plain text, HTML-formatted, and document attachments

### HTTP API
- Protocol: REST over HTTP (localhost:8120, use Cloudflare Tunnel for remote access)
- Auth: API key via `X-API-Key` header
- Responses: JSON

## Configuration
- `config.yaml`: servers, containers, stacks, services, scripts, thresholds, feature flags, API settings
- `.env`: secrets (bot token, chat IDs, WoL settings, API key)
- Hot-reloadable: edit config.yaml without restart

## Integration Points
- Docker Engine API via socket mount
- Host systemd via D-Bus socket mount
- External scripts via configurable paths (update-containers.sh, backup.sh)
- Log files via configurable paths

## Deployment
- Docker Compose (recommended) -- bot, monitoring, and API services
- Native Python with pip install (alternative)
