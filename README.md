# Linux Server Bot

Telegram bot for managing and monitoring Linux servers. Works together with [linux-server-management-scripts](https://github.com/Made-By-Adem/linux-server-management-scripts) for a complete server management ecosystem.

Tested on Ubuntu 22.04/22.10 and Raspberry Pi 5, but should work on any Linux server. Ideal for a single server running Docker containers and services that you want to monitor and control on the fly.

## Features

### Bot (interactive via Telegram)
- **Docker container management** - start, stop, restart individual or all containers
- **Docker Compose stack management** - up, down, restart, pull & recreate, view logs
- **Systemd service management** - start, stop, restart, status
- **Container updates** - trigger update script with dry-run, rollback support
- **Remote backup** - trigger backup script, view status and disk usage
- **Security overview** - Fail2ban, UFW, SSH sessions, failed logins, available updates
- **System info** - CPU, memory, disk, temperature, fan state, uptime
- **Server/website ping** - check reachability with state tracking
- **Log viewer** - browse and download configured log files
- **Custom commands** - execute shell commands via Telegram
- **Wake-on-LAN** - wake devices on the same network
- **Stress test** - run CPU stress tests (requires stress-ng)
- **Fan control** - toggle fan state
- **Server reboot** - with confirmation
- **Config reload** - hot-reload config without restart

### Monitoring (automatic, configurable interval)
- Docker container health + auto-restart
- Systemd service health + auto-restart
- Server/website reachability with retry
- CPU usage with double-verification
- Temperature monitoring with fan state
- Storage usage thresholds
- Failed SSH login detection (brute force alerts)
- Fail2ban ban notifications
- Push notifications for all alerts

## Architecture

```
Bot + Monitoring ──> Docker Socket ──> Containers
                 ──> D-Bus Socket  ──> Systemd Services
                 ──> Shell Scripts ──> Container Updates / Backups
                 ──> netcat        ──> Server Pings
```

Both services share a single `config.yaml` with hot-reload support via watchdog.

## Quick Start (Docker)

```bash
git clone https://github.com/MadeByAdem/Linux-server-Telegram-bot
cd Linux-server-Telegram-bot

# Configure
cp .env.example .env           # Set bot token, chat ID, WoL settings
cp config.example.yaml config.yaml  # Adjust services, containers, servers, etc.

# Deploy
docker compose up -d

# Chat with your bot
# Send /menu to get started
```

## Quick Start (Native Python)

```bash
git clone https://github.com/MadeByAdem/Linux-server-Telegram-bot
cd Linux-server-Telegram-bot

# Install
pip install -e .

# Configure
cp .env.example .env
cp config.example.yaml config.yaml

# Run
linux-bot        # Start the bot
linux-monitor    # Start monitoring (in another terminal)
```

## Prerequisites

- Python 3.10+ (or Docker)
- Telegram bot token from [@BotFather](https://t.me/BotFather)
- Your Telegram chat ID from [@RawDataBot](https://t.me/raw_data_bot)
- `netcat-traditional` - for server ping checks
- `etherwake` - for Wake-on-LAN (optional)
- `stress-ng` - for stress tests (optional)

```bash
sudo apt update && sudo apt install netcat-traditional etherwake stress-ng
```

## Configuration

### .env (secrets)

```env
SECRET_TOKEN=your_bot_token
CHAT_ID_PERSON1=your_chat_id
WOL_ADDRESS=aa:bb:cc:dd:ee:ff
WOL_HOSTNAME=my-device
```

### config.yaml (everything else)

All settings are in `config.yaml` with `${VAR}` syntax for environment variable references. See `config.example.yaml` for a complete reference.

Key sections:

| Section | Description |
|---------|-------------|
| `telegram` | Bot token and allowed user IDs |
| `features` | Toggle features on/off (hides menu buttons) |
| `services` | Systemd services manageable via bot |
| `containers` | Docker containers shown in bot menus |
| `compose_stacks` | Docker Compose stacks with name and path |
| `servers` | Servers to ping (name, host, port) |
| `logfiles` | Log file paths or directories |
| `scripts` | Paths to update-containers and backup scripts |
| `monitoring` | Interval, containers/services/servers to monitor, thresholds |

**Hot-reload**: Edit `config.yaml` while the bot is running -- changes are picked up automatically. Use `/reload` in Telegram to trigger a manual reload.

## Integration with linux-server-management-scripts

Configure script paths in `config.yaml`:

```yaml
scripts:
  update_containers: /opt/scripts/update-containers.sh
  backup: /opt/scripts/backup.sh
```

The bot provides Telegram menus to trigger these scripts with output streaming, dry-run support, and rollback options.

## Migration from v1

If upgrading from the text-file configuration:

```bash
python tools/migrate_config.py
```

This reads your existing `.txt` files and `.env` to generate a `config.yaml`.

## Project Structure

```
src/linux_server_bot/
    config.py              # YAML config + watchdog hot-reload
    bot/
        app.py             # Bot entrypoint
        menus.py           # Keyboard builder helpers
        handlers/          # One module per feature
    monitoring/
        app.py             # Monitoring scheduler
        checks/            # One module per check type
    shared/
        shell.py           # Safe subprocess wrappers
        auth.py            # Authorization decorator
        telegram.py        # Messaging helpers
        logging_setup.py   # Log rotation setup
```

## Development

```bash
pip install -e ".[dev]"
ruff check src/
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/menu` | Show interactive menu |
| `/services` | Service management |
| `/docker` | Docker container management |
| `/logs` | View log files |
| `/ping` | Ping configured servers |
| `/command` | Execute a shell command |
| `/sysinfo` | System information |
| `/wakewol` | Wake-on-LAN |
| `/reboot` | Reboot server (with confirmation) |
| `/reload` | Reload config without restart |

## Contributing

Feel free to submit issues or pull requests. Please follow the existing coding style.

## License

This project is licensed under the Custom License. See the [LICENSE](LICENSE) file for details.
