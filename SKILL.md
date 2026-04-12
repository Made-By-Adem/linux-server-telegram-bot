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

## Interaction Model
- Protocol: Telegram Bot API (polling mode)
- Navigation: Menu-driven via ReplyKeyboardMarkup
- Auth: User must be in allowed_users list in config.yaml
- Responses: Plain text, HTML-formatted, and document attachments

## Configuration
- `config.yaml`: servers, containers, stacks, services, scripts, thresholds, feature flags
- `.env`: secrets (bot token, chat IDs, WoL settings)
- Hot-reloadable: edit config.yaml without restart

## Integration Points
- Docker Engine API via socket mount
- Host systemd via D-Bus socket mount
- External scripts via configurable paths (update-containers.sh, backup.sh)
- Log files via configurable paths

## Deployment
- Docker Compose (recommended)
- Native Python with pip install (alternative)
