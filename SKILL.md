# SKILL: Linux Server Bot

## Description

Telegram bot for managing Docker containers, Compose stacks, systemd services,
and monitoring Linux server health. Includes an HTTP API for multi-server
management and AI agent integration. Integrates with
[linux-server-management-scripts](https://github.com/Made-By-Adem/linux-server-management-scripts)
for container updates and remote backups.

## Architecture

```
Bot        ──┐
Monitoring ──┤──> shared/actions/ ──> Docker Socket / D-Bus / Shell / netcat
API        ──┘
```

Three services share one `config.yaml` (hot-reloadable) and a common
`shared/actions/` business logic layer. Each service can run independently.

## Capabilities

### Telegram Bot Commands

| Command | Description | Parameters |
|---------|-------------|------------|
| /menu | Show interactive menu | none |
| /docker | Docker container management | none |
| /services | Systemd service management | none |
| /compose | Docker Compose stack management | none |
| /security | Security overview | none |
| /updates | Container updates (dry-run/run/rollback) | none |
| /backups | Trigger backup, view status/size | none |
| /ping | Ping configured servers | none |
| /sysinfo | System CPU/memory/disk/temp | none |
| /logs | View configured log files | none |
| /command | Execute shell command | interactive |
| /wakewol | Wake on LAN device | none |
| /reboot | Reboot host server | confirmation |
| /reload | Reload config without restart | none |

### Automated Monitoring

- Container health monitoring (auto-detected from Docker, configurable policy per container: notify / notify+restart / ignore)
- Service health monitoring (auto-detected from systemd enabled services, same configurable policy)
- Server/website reachability with retry and state tracking
- CPU usage with double-verification + top process report
- Temperature monitoring with fan state
- Storage usage thresholds
- Failed SSH login detection (brute force alerts)
- Fail2ban ban notifications

### HTTP API

REST API for multi-server management and AI agent access.

**Connection:**
- Base URL: `http://localhost:8120` (expose via Cloudflare Tunnel for remote access)
- Auth: `X-API-Key` header (except `/api/health`)
- Content-Type: `application/json`

**Auto-docs:**
- Swagger UI: `/docs` (interactive testing)
- ReDoc: `/redoc`
- OpenAPI spec: `/openapi.json`

**Response format:**
All endpoints return JSON. Success responses include a `success: true` field.
Error responses use `success: false` with an `error` message.

```json
{"success": true, "data": [...]}
{"success": false, "error": "description"}
```

**HTTP error codes:**

| Code | Meaning |
|------|---------|
| 200 | Success (check `success` field for application-level errors) |
| 403 | Invalid API key |
| 422 | Invalid request body |
| 503 | API disabled or API key not configured |

**Endpoints:**

| Endpoint | Method | Description | Parameters |
|----------|--------|-------------|------------|
| `/api/health` | GET | Health check (no auth) | |
| `/api/docker/status` | GET | All container statuses | |
| `/api/docker/{action}/{name}` | POST | Container action | action: `start`\|`stop`\|`restart` |
| `/api/docker/{action}` | POST | Bulk container action | action: `start_all`\|`stop_all`\|`restart_all` |
| `/api/docker/cleanup` | POST | Docker system prune | |
| `/api/logs` | GET | List available log files | |
| `/api/logs/{index}` | GET | Read log file tail | query: `?tail=50` |
| `/api/services/status` | GET | All service statuses | |
| `/api/services/{action}/{name}` | POST | Service action | action: `start`\|`stop`\|`restart` |
| `/api/compose/status` | GET | All stack statuses | |
| `/api/compose/{action}/{name}` | POST | Stack action | action: `up`\|`down`\|`restart`\|`pull` |
| `/api/compose/logs/{name}` | GET | Stack logs | query: `?tail=50` |
| `/api/sysinfo` | GET | Full system info (text) | |
| `/api/sysinfo/cpu` | GET | CPU usage % | |
| `/api/sysinfo/memory` | GET | Memory (total/used/free/cache MB) | |
| `/api/sysinfo/disk` | GET | Disk per partition | |
| `/api/sysinfo/temperature` | GET | CPU temperature | |
| `/api/sysinfo/stress-test` | POST | CPU stress test (feature-flag gated) | query: `?minutes=1` |
| `/api/sysinfo/fan` | POST | Set fan state (feature-flag gated) | query: `?state=0` (0=off/auto, 1=on) |
| `/api/security` | GET | Full security overview | |
| `/api/security/fail2ban` | GET | Fail2ban status | |
| `/api/security/ufw` | GET | UFW status | |
| `/api/security/ssh` | GET | SSH sessions | |
| `/api/security/failed-logins` | GET | Failed login attempts | |
| `/api/security/updates` | GET | Available updates | |
| `/api/servers/ping` | GET | Ping all configured servers | |
| `/api/wol` | POST | Send Wake-on-LAN packet | |
| `/api/updates/dry-run` | POST | Preview container updates | |
| `/api/updates/run` | POST | Run container updates | |
| `/api/updates/rollback` | POST | Rollback container updates | |
| `/api/backups/trigger` | POST | Trigger backup | |
| `/api/backups/status` | GET | Backup status | |
| `/api/backups/size` | GET | Backup disk usage | |
| `/api/command` | POST | Execute shell command | body: `{"command": "..."}` (60s timeout) |
| `/api/reboot` | POST | Reboot server | body: `{"confirm": true}` |
| `/api/config/reload` | POST | Reload config.yaml | |

For detailed request/response schemas with examples, see [`agent/ENDPOINTS.md`](agent/ENDPOINTS.md).

## AI Agent Integration

The [`agent/`](agent/) directory contains a self-contained kit for AI agent integration:

| File | Purpose |
|------|---------|
| `agent/SKILL.md` | Concise skill prompt optimized for AI agent system prompts |
| `agent/ENDPOINTS.md` | Complete endpoint reference with request/response JSON schemas |
| `agent/workflows.md` | Step-by-step workflow recipes (health check, security audit, updates, etc.) |
| `agent/.env.example` | Multi-server environment configuration for agents |
| `agent/README.md` | Setup guide for agent integration |

## Interaction Model

### Telegram Bot
- Protocol: Telegram Bot API (polling mode)
- Navigation: Persistent ReplyKeyboard (main menu) + InlineKeyboard (actions)
- Auth: User must be in `allowed_users` list in config.yaml
- Responses: Plain text, HTML-formatted, and document attachments

### HTTP API
- Protocol: REST over HTTP (localhost:8120)
- Auth: API key via `X-API-Key` header
- Responses: JSON
- Remote access: Cloudflare Tunnel (recommended)

## Configuration
- `config.yaml`: servers, compose stacks, scripts, thresholds, feature flags, API settings, log files, per-item failure policies
- `.env`: secrets (bot token, chat IDs, WoL settings, API key -- auto-generated on first run)
- Services and containers are auto-detected; config entries are only needed to override the default failure policy
- Hot-reloadable: edit config.yaml at runtime, changes are picked up via watchdog (0.5s debounce) or `/reload` command
- First-run setup wizard with resume support for interactive .env configuration

## Integration Points
- Docker Engine API via socket mount (`/var/run/docker.sock`)
- Host systemd via D-Bus socket mount (`/var/run/dbus/system_bus_socket`)
- External scripts via configurable paths (`update-containers.sh`, `backup.sh`)
- Log files via configurable paths (supports files, directories, and glob patterns)
- Server pings via netcat

## Startup & Deployment
- First-run setup wizard: 4-step interactive flow (bot token → chat ID → API key → WoL), with state tracking so interrupted setup resumes from where it left off
- Bot token validation via Telegram `getMe` API before startup
- Preflight checks: Docker socket access, config file presence
- API key auto-generated on first run (no manual key creation)
- API port auto-detection: tries configured port, scans next 20 if busy, interactive prompt as fallback, or skip API entirely
- Atomic `.env` writes (temp file + rename) to prevent corruption on interruption
- Graceful shutdown: SIGINT/SIGTERM handled cleanly without stack traces
- Startup banner: shows active features, monitoring config, and API port
- Docker Compose (recommended): bot, monitoring, and API as three services
- Native Python: `pip install -e .` with three entry points (`linux-bot`, `linux-monitor`, `linux-api`)
