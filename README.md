# Linux Server Bot

Manage and monitor your Linux server from your phone via Telegram. Start, stop and restart Docker containers and services, check security logs, view system resources, trigger backups -- all without opening an SSH session.

Tested on Ubuntu 22.04/22.10 and Raspberry Pi 5, but should work on any Linux server.

> [!TIP]
> **Setting up a new server?** Use [linux-server-management-scripts](https://github.com/Made-By-Adem/linux-server-management-scripts) first to harden your server (SSH, firewall, Fail2ban, Docker, and 17 security layers), then deploy this bot for ongoing management. The bot integrates directly with the update and backup scripts from that repo.

### What can you do with it?

- **Manage Docker** -- start, stop, restart containers and Compose stacks from Telegram
- **Manage services** -- control systemd services (nginx, docker, ufw, etc.)
- **Get automatic alerts** -- the bot watches your server in the background and notifies you when a container crashes, a service goes down, CPU spikes, disk fills up, or someone tries to brute-force SSH. You choose per service and container what should happen: just notify, notify and auto-restart, or ignore.
- **Check security** -- view Fail2ban bans, UFW rules, SSH sessions, failed logins, and available updates
- **View system info** -- CPU, memory, disk, temperature, uptime
- **Browse logs** -- read rkhunter scans, auth.log, fail2ban, syslog, and more directly in Telegram
- **Trigger updates & backups** -- run your update and backup scripts with dry-run and rollback support
- **Ping servers** -- check if your other servers and websites are reachable
- **Execute commands** -- run any shell command from Telegram when you need it
- **Wake-on-LAN** -- wake devices on the same network

Everything happens in **one Telegram chat** -- the bot sends you alerts automatically, and you use the interactive menu to manage your server whenever you need to.

> [!NOTE]
> Most users only need the Telegram bot. The **HTTP API** is an optional extra for advanced use cases like multi-server dashboards, automation, or AI agent integration. When enabled, it runs on localhost and can be securely exposed over HTTPS via [Cloudflare Tunnel](#-cloudflare-tunnel-setup-optional).

---

## 📦 How It Works

The bot has two sides, both in the same Telegram chat:

### 🎛️ Interactive Menu

Open the menu with `/menu` or a bot command and manage your server on-demand: start/stop containers, check security, view logs, trigger updates, etc. The main menu stays visible at the bottom of the chat, with inline buttons for actions.

**What you can control:** Docker containers, Compose stacks, systemd services, security overview, system info, log viewer, server ping, container updates, backups, custom commands, Wake-on-LAN, stress test, fan control, reboot, config reload.

### 📡 Background Monitoring

The bot continuously watches your server and sends you a message when something needs attention. New containers and services are **auto-detected** -- no manual configuration needed.

**What it monitors:**

| Check | What happens |
|-------|-------------|
| Docker containers | Auto-detected, configurable per container: notify, notify + restart, or ignore |
| Systemd services | Auto-detected (all enabled services), same configurable policy |
| Server/website ping | Alert when a server goes offline or comes back online |
| CPU usage | Alert when CPU exceeds threshold (double-verified, shows top processes) |
| Temperature | Alert when temperature exceeds threshold (reports fan state) |
| Disk usage | Alert when storage exceeds threshold |
| SSH failed logins | Alert on brute force attempts (>10 failures) |
| Fail2ban bans | Alert when an IP gets banned |

Containers and services are auto-detected at each monitoring cycle. Failure policies can be changed per item via the Telegram bot menu or in `config.yaml`. Monitoring interval, thresholds, and servers to ping are configurable in `config.yaml`.

### 🌐 HTTP API (Optional)

For advanced users: a REST API that exposes all bot functionality as HTTP endpoints. Useful if you want to build a dashboard, integrate with other tools, or let an AI agent manage multiple servers.

- REST API on `localhost:8120` with API key authentication
- Swagger UI at `/docs` for interactive exploration
- Designed for Cloudflare Tunnel exposure (no open ports needed)
- See [`agent/`](agent/) for AI agent integration kit

---

## 🏗️ Architecture

Under the hood, the bot runs as two processes (interactive + monitoring) that share the same config and business logic. The optional API is a third process.

```
Telegram Chat
  ├── Interactive menu  ──┐
  └── Monitoring alerts ──┤──> shared/actions/ ──> Docker Socket ──> Containers
                          │                    ──> D-Bus Socket  ──> Systemd Services
  HTTP API (optional)  ───┘                    ──> Shell Scripts ──> Updates / Backups
                                               ──> netcat        ──> Server Pings
```

All processes share a single `config.yaml` with hot-reload support (edit while running, changes are picked up automatically).

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

Then deploy (this starts the bot, monitoring, and API together):

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

linux-bot        # Start the interactive bot
linux-monitor    # Start background monitoring (in another terminal)
linux-api        # Start the HTTP API (optional, in another terminal)
```

> [!TIP]
> On first run, the bot launches an interactive **setup wizard** that walks you through configuring your bot token, chat ID, and optional settings. An API key is generated automatically. If the setup is interrupted, it resumes where you left off next time.

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
| `API_KEY` | No | API key for HTTP API access. **Generated automatically** on first API startup -- you don't need to set this yourself |

### config.yaml (Everything Else)

All settings are in `config.yaml` with `${VAR}` syntax for environment variable references. See `config.example.yaml` for a complete reference.

> [!TIP]
> The bot works out of the box with just the `.env` configured. Edit `config.yaml` to customize which containers, services, servers, and log files appear in the bot menus.

**Key sections:**

| Section | What to configure | Default |
|---------|-------------------|---------|
| `features` | Toggle features on/off (hides menu buttons) | All enabled |
| `services` | Extra services for bot menu (auto-detected by default) | -- |
| `containers` | Extra containers for bot menu (auto-detected by default) | -- |
| `compose_stacks` | Docker Compose stacks with name and path | Example stack |
| `servers` | Servers to ping (name, host, port) | Example server |
| `logfiles` | Log file paths, directories, or glob patterns | Security + system logs |
| `scripts` | Paths to update-containers and backup scripts | /opt/scripts/ |
| `api` | API enabled/port/key for HTTP API | Enabled on port 8120 |
| `monitoring` | Interval, thresholds, per-item failure policies | 5 min, auto-detect |

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

## 🔍 Features Overview

| Feature | Interactive (menu) | Automatic (monitoring) | API (optional) |
|---------|-------------------|----------------------|----------------|
| Docker containers | Start, stop, restart, status, policy | Auto-detected, configurable policy | All actions via HTTP |
| Systemd services | Start, stop, restart, status, policy | Auto-detected, configurable policy | All actions via HTTP |
| Compose stacks | Up, down, restart, pull, logs | -- | All actions via HTTP |
| System info | On-demand overview | CPU, temp & disk alerts | On-demand via HTTP |
| Security | Full overview on request | Brute force & ban alerts | Full overview via HTTP |
| Server ping | On-demand check | Continuous reachability | On-demand via HTTP |
| Container updates | Dry-run, update, rollback | -- | Via HTTP |
| Backups | Trigger, status, disk usage | -- | Via HTTP |
| Log viewer | Browse & download files | -- | -- |
| Custom commands | Execute any shell command | -- | Via HTTP |
| Wake-on-LAN | Wake device | -- | Via HTTP |

---

## 🌐 HTTP API

The API runs on `localhost:8120` only -- it's not directly exposed to the internet. For remote access, expose it securely over HTTPS via [Cloudflare Tunnel](#-cloudflare-tunnel-setup-optional). All endpoints (except `/api/health`) require the `X-API-Key` header.

A secure API key is **generated automatically** on first startup and saved to your `.env` file. You can find it there with `grep API_KEY .env`.

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

### 🔒 Cloudflare Tunnel Setup (Optional)

The API runs on `localhost:8120` -- it's **not exposed to the internet** by default. To access it remotely (e.g., from an AI agent or another server), use a Cloudflare Tunnel. This gives you HTTPS without opening any ports on your firewall.

> [!TIP]
> If you used [linux-server-management-scripts](https://github.com/Made-By-Adem/linux-server-management-scripts) to set up your server, you may already have a `cloudflared` container running. You can use that existing tunnel to expose the API.

**Step 1: Add a route for the API**

If you're using a `cloudflared` config file, add a new ingress rule:

```yaml
# /etc/cloudflared/config.yml
ingress:
  - hostname: api-myserver.example.com
    service: http://localhost:8120
  # ... your other routes ...
  - service: http_status:404
```

Then restart cloudflared to apply:

```bash
docker restart cloudflared
# or: sudo systemctl restart cloudflared
```

**Step 2: Add the DNS record in Cloudflare Dashboard**

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/) → your domain → **DNS**
2. Add a **CNAME** record:
   - **Name:** `api-myserver` (or whatever subdomain you chose)
   - **Target:** your tunnel ID (e.g., `xxxxxxxx-xxxx-xxxx-xxxx.cfargotunnel.com`)
   - **Proxy:** enabled (orange cloud)

If you're using the Cloudflare Tunnel dashboard instead of a config file:
1. Go to **Zero Trust** → **Networks** → **Tunnels**
2. Click your tunnel → **Configure**
3. Add a **Public Hostname**:
   - **Subdomain:** `api-myserver`
   - **Domain:** your domain
   - **Service:** `http://localhost:8120`

**Step 3: Test it**

```bash
# Should return {"status": "healthy", "version": "2.0.0"}
curl https://api-myserver.example.com/api/health

# Authenticated request
curl -H "X-API-Key: your-key" https://api-myserver.example.com/api/docker/status
```

Your API is now accessible over HTTPS at `https://api-myserver.example.com`.

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
        startup.py         # Setup wizard, preflight checks, graceful shutdown
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

If you're upgrading from the old version of this bot (which used `.txt` files like `bot_services.txt`, `bot_servers.txt`, etc.), you can automatically convert your existing configuration to the new `config.yaml` format:

```bash
python tools/migrate_config.py
```

This reads your old `.txt` config files and `.env`, and generates a `config.yaml` with all your settings. Review the output and adjust as needed.

> [!NOTE]
> This is a one-time migration tool. New installations don't need this -- just edit `config.yaml` directly.

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

# Services and containers are auto-detected.
# Check if the failure policy is not set to 'ignore':
# Look in config.yaml under monitoring.services / monitoring.containers
# or check via the Policy button in the Telegram bot menu.
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
