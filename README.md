# Linux Server Bot

Telegram bot for managing and monitoring Linux servers. Works together with [linux-server-management-scripts](https://github.com/Made-By-Adem/linux-server-management-scripts) for a complete server management ecosystem.

Tested on Ubuntu 22.04/22.10 and Raspberry Pi 5, but should work on any Linux server. Ideal for a single server running Docker containers and services that you want to monitor and control on the fly.

---

## 📦 What's Inside?

This repository contains three complementary services:

### 1. Bot (Interactive via Telegram)

Control your server from your phone with an interactive menu and inline buttons.

**Key Features:**

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

---

### 2. Monitoring (Automatic, Configurable Interval)

Runs in the background and sends push notifications when something needs attention.

**Key Features:**

- Docker container health + auto-restart
- Systemd service health + auto-restart
- Server/website reachability with retry
- CPU usage with double-verification
- Temperature monitoring with fan state
- Storage usage thresholds
- Failed SSH login detection (brute force alerts)
- Fail2ban ban notifications
- Push notifications for all alerts

---

### 3. HTTP API (Multi-Server Management)

REST API for automation and AI agent integration across multiple servers.

**Key Features:**

- **REST API** on `localhost:8120` with API key authentication
- All bot functionality available as HTTP endpoints
- Swagger UI at `/docs` for interactive exploration
- Designed for Cloudflare Tunnel exposure (no open ports needed)
- Ideal for AI agent / automation integration across multiple servers

---

## 🏗️ Architecture

```
Bot        ──┐
Monitoring ──┤──> shared/actions/ ──> Docker Socket ──> Containers
API        ──┘                   ──> D-Bus Socket  ──> Systemd Services
                                 ──> Shell Scripts ──> Container Updates / Backups
                                 ──> netcat        ──> Server Pings
```

All three services (bot, monitoring, API) share a single `config.yaml` with hot-reload support via watchdog, and use the same `shared/actions/` layer for business logic.

---

## 🚀 Quick Start

### 1. Get your Telegram credentials

Before you begin, you need two things from Telegram:

1. **Bot token** -- Talk to [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`, follow the prompts, and copy the token it gives you
2. **Your chat ID** -- Talk to [@RawDataBot](https://t.me/raw_data_bot) on Telegram, send `/start`, and copy the `chat_id` number from the response

### 2. Deploy

#### Docker (Recommended)

```bash
git clone https://github.com/MadeByAdem/Linux-server-Telegram-bot
cd Linux-server-Telegram-bot

# Copy example configs
cp .env.example .env
cp config.example.yaml config.yaml
```

Now edit `.env` with your credentials:

```env
SECRET_TOKEN=paste_your_bot_token_here
CHAT_ID_PERSON1=paste_your_chat_id_here
```

> [!NOTE]
> That's all you need to get started. The other `.env` variables (WoL, API key) are optional -- you can configure them later.

Then deploy:

```bash
docker compose up -d
```

#### Native Python (Alternative)

```bash
git clone https://github.com/MadeByAdem/Linux-server-Telegram-bot
cd Linux-server-Telegram-bot
pip install -e .

cp .env.example .env
cp config.example.yaml config.yaml
# Edit .env with your bot token and chat ID (see above)

linux-bot        # Start the bot
linux-monitor    # Start monitoring (in another terminal)
linux-api        # Start the HTTP API (in another terminal)
```

### 3. Start chatting

1. Open Telegram and search for your bot by the name you gave it in BotFather
2. Press **Start** or send `/start`
3. Send `/menu` to open the interactive menu

The bot comes with sensible defaults in `config.example.yaml` -- you can customize containers, services, servers, and more in `config.yaml` whenever you're ready.

---

## 📋 Requirements

### System Requirements

- **OS:** Ubuntu 20.04+ or Debian 11+ (including Raspberry Pi OS)
- **Python:** 3.10+ (or Docker)
- **Shell:** Bash 4.0+

### Optional System Packages

Only needed if running natively (Docker image includes these):

- `netcat-traditional` - for server ping checks
- `etherwake` - for Wake-on-LAN
- `stress-ng` - for stress tests

```bash
sudo apt update && sudo apt install netcat-traditional etherwake stress-ng
```

---

## 🔧 Configuration

### .env (Secrets)

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_TOKEN` | **Yes** | Telegram bot token from @BotFather |
| `CHAT_ID_PERSON1` | **Yes** | Your Telegram chat ID from @RawDataBot |
| `WOL_ADDRESS` | No | MAC address for Wake-on-LAN |
| `WOL_HOSTNAME` | No | Hostname for WoL device |
| `API_KEY` | No | API key for HTTP API access (required if you enable the API) |

### config.yaml (Everything Else)

All settings are in `config.yaml` with `${VAR}` syntax for environment variable references. See `config.example.yaml` for a complete reference.

> [!TIP]
> The bot works out of the box with just the `.env` configured. Edit `config.yaml` to customize which containers, services, servers, and log files appear in the bot menus.

**Key sections:**

| Section | What to configure | Default |
|---------|-------------------|---------|
| `features` | Toggle features on/off (hides menu buttons) | All enabled |
| `services` | Systemd services manageable via bot | docker, ufw, nginx |
| `containers` | Docker containers shown in bot menus | portainer, nginx |
| `compose_stacks` | Docker Compose stacks with name and path | Example stack |
| `servers` | Servers to ping (name, host, port) | Example server |
| `logfiles` | Log file paths, directories, or glob patterns | Security + system logs |
| `scripts` | Paths to update-containers and backup scripts | /opt/scripts/ |
| `api` | API enabled/port/key for HTTP API | Enabled on port 8120 |
| `monitoring` | Interval, targets, thresholds | 5 min interval |

**Hot-reload**: Edit `config.yaml` while the bot is running -- changes are picked up automatically. Use `/reload` in Telegram to trigger a manual reload.

---

## 📖 Common Workflows

### Scenario 1: Fresh Server Setup with Bot

> [!IMPORTANT]
> Use [linux-server-management-scripts](https://github.com/Made-By-Adem/linux-server-management-scripts) for initial server setup and hardening, then deploy this bot for ongoing management.

```bash
# 1. Set up your server with the baseline script
cd linux-server-management-scripts/server-baseline
sudo bash install-script.sh --fresh-install

# 2. Deploy the Telegram bot
cd ~/Linux-server-Telegram-bot
cp .env.example .env && cp config.example.yaml config.yaml
# Edit .env and config.yaml with your settings
docker compose up -d
```

### Scenario 2: Automated Container Updates via Bot

```bash
# Configure script paths in config.yaml
scripts:
  update_containers: /opt/scripts/update-containers.sh
  backup: /opt/scripts/backup.sh
```

Then use the bot's **Updates** menu to trigger dry-run, update, or rollback -- all from your phone.

### Scenario 3: Multi-Server Management via API

```bash
# Enable the API in config.yaml
api:
  enabled: true
  port: 8120
  api_key: "${API_KEY}"

# Expose via Cloudflare Tunnel for remote access
# Then manage multiple servers from a single dashboard or AI agent
```

---

## 🔍 Features Comparison

| Feature | Bot | Monitoring | API |
|---------|-----|------------|-----|
| Docker management | ✅ | ✅ (health checks) | ✅ |
| Service management | ✅ | ✅ (health checks) | ✅ |
| Compose stacks | ✅ | ❌ | ✅ |
| System info | ✅ | ✅ (alerts) | ✅ |
| Security overview | ✅ | ✅ (brute force alerts) | ✅ |
| Server ping | ✅ | ✅ (reachability) | ✅ |
| Wake-on-LAN | ✅ | ❌ | ✅ |
| Custom commands | ✅ | ❌ | ✅ |
| Log viewer | ✅ | ❌ | ❌ |
| Auto-restart | ❌ | ✅ | ❌ |
| Push notifications | ❌ | ✅ | ❌ |
| Swagger UI | ❌ | ❌ | ✅ |

---

## 🌐 HTTP API

The API runs on `localhost:8120` and is designed to be exposed via Cloudflare Tunnel. All endpoints (except `/api/health`) require the `X-API-Key` header.

```bash
# Health check (no auth)
curl http://localhost:8120/api/health

# Get container status
curl -H "X-API-Key: your-key" http://localhost:8120/api/docker/status

# Restart a container
curl -X POST -H "X-API-Key: your-key" http://localhost:8120/api/docker/restart/nginx

# Interactive docs
open http://localhost:8120/docs
```

See [SKILL.md](SKILL.md) for the complete endpoint reference.

### AI Agent Integration

The [`agent/`](agent/) directory contains a self-contained kit for integrating AI agents with the API: skill prompts, endpoint schemas with response examples, workflow recipes, and multi-server `.env` configuration. See [`agent/README.md`](agent/README.md) for setup instructions.

### Cloudflare Tunnel Setup

Add to your existing tunnel config:

```yaml
# /etc/cloudflared/config.yml
ingress:
  - hostname: api-myserver.example.com
    service: http://localhost:8120
```

---

## 🤖 Bot Commands

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

---

## 🗂️ Project Structure

```
src/linux_server_bot/
    config.py              # YAML config + watchdog hot-reload
    bot/
        app.py             # Bot entrypoint
        menus.py           # Keyboard builder helpers
        callbacks.py       # Central InlineKeyboard callback router
        handlers/          # One module per feature
    monitoring/
        app.py             # Monitoring scheduler
        checks/            # One module per check type
    api/
        server.py          # FastAPI app + uvicorn entrypoint
        auth.py            # API key authentication
        routes.py          # All REST endpoints
    shared/
        shell.py           # Safe subprocess wrappers
        auth.py            # Authorization decorator
        telegram.py        # Messaging helpers
        logging_setup.py   # Log rotation setup
        actions/           # Business logic shared by bot + API
```

---

## 🔄 Integration with linux-server-management-scripts

This bot is designed to work alongside [linux-server-management-scripts](https://github.com/Made-By-Adem/linux-server-management-scripts) for container updates and remote backups. Here's how to set it up:

```bash
# 1. Clone the scripts repo on your server
git clone https://github.com/Made-By-Adem/linux-server-management-scripts.git /opt/scripts-repo

# 2. Make scripts executable
chmod +x /opt/scripts-repo/update-containers/update-containers.sh
chmod +x /opt/scripts-repo/backup-script/backup.sh

# 3. Symlink to /opt/scripts (or update paths in config.yaml)
sudo mkdir -p /opt/scripts
sudo ln -sf /opt/scripts-repo/update-containers/update-containers.sh /opt/scripts/update-containers.sh
sudo ln -sf /opt/scripts-repo/backup-script/backup.sh /opt/scripts/backup.sh
```

Then configure the paths in `config.yaml`:

```yaml
scripts:
  update_containers: /opt/scripts/update-containers.sh
  backup: /opt/scripts/backup.sh
```

The bot provides Telegram menus to trigger these scripts with output streaming, dry-run support, and rollback options.

> [!NOTE]
> This integration is optional. If you don't need container updates or backups via the bot, you can skip this and disable the features in `config.yaml` under `features`.

---

## 🔀 Migration from v1

If upgrading from the text-file configuration:

```bash
python tools/migrate_config.py
```

This reads your existing `.txt` files and `.env` to generate a `config.yaml`.

---

## 🛠️ Development

```bash
pip install -e ".[dev]"
ruff check src/
```

---

## 🐛 Troubleshooting

### Common Issues

**Bot not responding to commands**

```bash
# Check if the bot is running
docker compose ps

# View bot logs
docker compose logs bot

# Verify your .env has the correct token and chat ID
cat .env | grep SECRET_TOKEN
cat .env | grep CHAT_ID
```

**"Permission denied" for Docker commands**

```bash
# The bot needs access to the Docker socket
# Ensure docker-compose.yml mounts /var/run/docker.sock
# If running natively, add the user to the docker group:
sudo usermod -aG docker $USER
```

**Config changes not picked up**

```bash
# Hot-reload should pick up changes automatically
# If not, send /reload in Telegram or restart:
docker compose restart bot
```

**Monitoring not sending alerts**

```bash
# Check monitoring logs
docker compose logs monitor

# Verify monitoring section in config.yaml
# Ensure containers/services/servers are listed under monitoring
```

**API returning 403 Forbidden**

```bash
# Verify your API key matches
curl -H "X-API-Key: your-key" http://localhost:8120/api/health

# Check .env has API_KEY set
# Check config.yaml has api.api_key: "${API_KEY}"
```

For more specific issues, check the logs in the `logs/` directory.

---

## 📄 License

This project is licensed under the Custom License - see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer

**USE AT YOUR OWN RISK**

This bot executes system commands and manages Docker containers and services. While designed with safety in mind:

- **Test in development first:** Always verify on a non-production server
- **Understand what you're running:** Read the documentation
- **Restrict access:** Only add trusted Telegram user IDs to `allowed_users`
- **Secure the API:** Use strong API keys and Cloudflare Tunnel for remote access
- **No guarantees:** We're not responsible for data loss or downtime

For enterprise or critical systems, consult a professional DevOps engineer.

---

## 🌟 Acknowledgments

Built with focus on:

- **Safety:** Authorization checks, confirmation dialogs, and restricted access
- **Usability:** Interactive menus with inline buttons for quick actions
- **Reliability:** Tested on Ubuntu 22.04+, Raspberry Pi 5
- **Maintainability:** Modular architecture with shared actions layer

---

**Made with ❤️ by MadeByAdem**

If you find this bot useful, consider giving this repository a ⭐ on GitHub!

---

## 📚 Additional Resources

### Related Projects

- [linux-server-management-scripts](https://github.com/Made-By-Adem/linux-server-management-scripts) - Server setup, hardening, container updates & backup scripts

### Useful Links

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [pyTelegramBotAPI Documentation](https://pytba.readthedocs.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
