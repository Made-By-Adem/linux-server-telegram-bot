# Linux Server Bot

Telegram bot + REST API for managing and monitoring Linux servers. Control Docker containers and systemd services, get automatic health alerts, check security, view logs, and trigger backups -- all from Telegram or via API.

The API makes this bot a natural fit for **AI agents**: give your agent the [skill file](agent/SKILL.md) and it can manage your servers autonomously -- restart crashed containers, run security audits, trigger updates, and more. See the [`agent/`](agent/) directory for a ready-to-use integration kit with workflows and endpoint documentation.

```
Telegram Chat ──── Bot ──────┐
                             ├──> shared/actions/ ──> Docker / systemd / shell
AI Agent ─────── REST API ───┘
                               ▲ single config.yaml (hot-reloadable)
```

Tested on Ubuntu 24.04, Debian 12, and Raspberry Pi 5, but should work on any Linux server.

> [!TIP]
> **Setting up a new server?** Use [linux-server-management-scripts](https://github.com/Made-By-Adem/linux-server-management-scripts) first to harden your server (SSH, firewall, Fail2ban, Docker, and 17 security layers), then deploy this bot for ongoing management.

### What can you do with it?

- **Manage Docker** -- start, stop, restart containers
- **Manage Docker Compose stacks** -- up, down, restart, pull images, view logs
- **Manage services** -- control systemd services (nginx, docker, ufw, etc.)
- **Get automatic alerts** -- monitors containers, services, CPU, disk, temperature, SSH brute-force, and Fail2ban. Configurable per item: notify, notify + auto-restart, or ignore.
- **Check security** -- Fail2ban bans, UFW rules, SSH sessions, failed logins, available updates
- **View system info** -- CPU, memory, disk, temperature, uptime
- **Browse logs** -- auth.log, fail2ban, syslog, rkhunter, and more (sent as .txt for easy mobile viewing)
- **Trigger updates & backups** -- with dry-run preview and rollback support
- **Ping servers** -- check if your other servers and websites are reachable
- **Execute commands** -- run any shell command when you need it
- **Run custom scripts** -- execute configured scripts with configurable timeouts
- **Manage settings** -- toggle features, adjust monitoring thresholds, and change failure policies from Telegram
- **REST API** -- every feature above is also available as an HTTP endpoint with Swagger docs, designed for dashboards, automation, and AI agent integration

Everything works from **one Telegram chat** (alerts + interactive menu), and optionally via the **HTTP API** for programmatic access.

> [!NOTE]
> Most users only need the Telegram bot. The **HTTP API** is an optional extra for multi-server dashboards, automation, or AI agent integration. When enabled, it runs on localhost and can be securely exposed via [Cloudflare Tunnel](#-cloudflare-tunnel-setup).

---

## 📦 How It Works

The bot has two sides, both in the same Telegram chat:

### 🎛️ Interactive Menu

Open the menu with `/menu` or a bot command and manage your server on-demand: start/stop containers, check security, view logs, trigger updates, etc. The main menu stays visible at the bottom of the chat, with inline buttons for actions.

**What you can control:** Docker containers, systemd services, security overview, system info, log viewer, server ping, container updates, backups, custom commands, stress test, fan control, reboot, config reload.

### 📡 Background Monitoring

The bot continuously watches your server and sends you a message when something needs attention. Only services and containers explicitly listed in `config.yaml` are monitored -- giving you full control over what gets checked.

**What it monitors:**

| Check | What happens |
|-------|-------------|
| Docker containers | Only configured containers, with per-item policy: notify, notify + restart, or ignore |
| Systemd services | Only configured services, same per-item policy |
| Server/website ping | Alert on state change (online/offline), not every cycle |
| CPU usage | Alert when CPU exceeds threshold (double-verified, shows top processes) |
| Temperature | Alert when temperature exceeds threshold (reports fan state) |
| Disk usage | Alert when storage exceeds threshold |
| SSH failed logins | Alert on brute force attempts (>10 failures) |
| Fail2ban bans | Alert when an IP gets banned |

Services and containers are configured in `config.yaml` under `services` and `containers` (one list each, used by both the bot menu and monitoring). You can add/remove items and change failure policies via the Telegram bot menu, the API, or directly in `config.yaml`.

### 🌐 HTTP API (Optional)

A REST API that exposes all bot functionality as HTTP endpoints, with Swagger docs at `/docs`.

- Runs on `localhost:8120` with API key authentication
- API key **generated automatically** on first startup (see [API Key](#api-key))
- Add/remove monitored services and containers via API
- See [`agent/ENDPOINTS.md`](agent/ENDPOINTS.md) for the full endpoint reference

---

## 🏗️ Architecture

The bot runs as three Docker containers (bot + monitoring + API) that share the same config and business logic.

```
Telegram Chat
  ├── Interactive menu  ──┐
  └── Monitoring alerts ──┤──> shared/actions/ ──> Docker Socket ──> Containers
                          │                    ──> nsenter + systemctl ──> Services
  HTTP API (optional)  ───┘                    ──> nsenter + shell     ──> Host Commands
                                               ──> netcat              ──> Server Pings
```

All processes share a single `config.yaml` with hot-reload support (edit while running, changes are picked up automatically).

> [!NOTE]
> **Docker host access**: The containers run in `privileged` mode with `pid: host`. Commands that need host binaries (systemctl, ufw, fail2ban-client, etc.) are automatically wrapped with `nsenter -t 1 -m --` to run in the host's mount namespace. This is transparent -- you don't need to do anything special.

---

## 🚀 Quick Start

### 1. Get your Telegram credentials

1. **Bot token** -- Talk to [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`, follow the prompts, and copy the token
2. **Your chat ID** -- Talk to [@RawDataBot](https://t.me/raw_data_bot) on Telegram, send `/start`, and copy the `chat_id` number

### 2. Deploy

```bash
git clone https://github.com/Made-By-Adem/linux-server-telegram-bot
cd linux-server-telegram-bot

# Copy example configs
cp .env.example .env
cp config.example.yaml config.yaml
```

Edit `.env` with the credentials from step 1:

```env
SECRET_TOKEN=paste_your_bot_token_here
CHAT_ID_PERSON1=paste_your_chat_id_here
# CHAT_ID_PERSON2=optional_second_user
```

Start all services:

```bash
docker compose up -d
```

Check the logs to verify everything started:

```bash
docker compose logs -f
```

### 3. Start chatting

1. Open Telegram and search for your bot by the name you gave it in BotFather
2. Press **Start** or send `/start`
3. Send `/menu` to open the interactive menu

---

## 🔧 Configuration

### .env (Secrets)

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_TOKEN` | **Yes** | Telegram bot token from @BotFather |
| `CHAT_ID_PERSON1` | **Yes** | Your Telegram chat ID from @RawDataBot |
| `CHAT_ID_PERSON2` | No | Second authorized user's chat ID |
| `API_KEY` | No | Auto-generated on first startup (see [API Key](#api-key)) |
| `WOL_ADDRESS` | No | MAC address for Wake-on-LAN (menu button hidden when empty) |
| `WOL_HOSTNAME` | No | Display name for the WoL device |

### config.yaml

All settings are in `config.yaml` with `${VAR}` syntax for environment variable references. Changes are picked up automatically (hot-reload). See [`config.example.yaml`](config.example.yaml) for a complete reference.

#### Services and containers

List the services and containers you want to manage and monitor. Only items listed here appear in the bot menu and are checked by the monitoring loop.

```yaml
# Systemd services
services:
  - name: docker
    on_failure: notify           # send alert only
  - name: ufw
    on_failure: notify
  - name: nginx
    on_failure: notify_restart   # send alert AND auto-restart

# Docker containers
containers:
  - name: portainer
    on_failure: notify_restart
  - name: my-app
    on_failure: notify
  - name: dev-container
    on_failure: ignore           # don't monitor
```

**Policy options:** `notify` (alert only), `notify_restart` (alert + auto-restart), `ignore` (skip).

Policies can be changed at runtime via the Telegram bot menu (Policy button) or via the API.

#### Servers to ping

```yaml
servers:
  - name: "My VPS"
    host: "1.2.3.4"
    port: 443

monitoring:
  servers:
    - name: "My VPS"
      host: "1.2.3.4"
      port: 443
```

The top-level `servers` list is for the bot menu (on-demand ping). The `monitoring.servers` list is for the background monitoring loop (state-change alerts).

#### Features toggle

Disable features to hide their menu buttons:

```yaml
features:
  docker_containers: true
  docker_compose: true    # disable if not using Compose stacks
  systemd_services: true
  server_ping: true
  security_overview: true
  custom_commands: true
  custom_scripts: true
  logs: true
  system_info: true
  container_updates: true
  backups: true
  wol: true              # also hidden when WOL_ADDRESS is empty
  stress_test: true
  fan_control: true
  reboot: true
  settings: true
```

#### Scripts

Point to your update and backup scripts. If you followed the [linux-server-management-scripts](https://github.com/Made-By-Adem/linux-server-management-scripts) setup, the scripts are at `/usr/local/bin/`:

```yaml
scripts:
  update_containers: /usr/local/bin/update-containers
  backup: /usr/local/bin/backup
```

#### Monitoring thresholds

```yaml
monitoring:
  interval_minutes: 5
  thresholds:
    cpu_percent: 80
    storage_percent: 90
    temperature_celsius: 50
```

Thresholds can also be changed via the Telegram bot (System info → Thresholds) or the API.

### API Key

The API key is **generated automatically** on first startup. When the bot detects the placeholder value `your-secret-api-key-here` in `.env`, it generates a secure random key and saves it back to `.env`.

To find your generated key:

```bash
grep API_KEY .env
```

To set a custom key, replace the value in `.env` and restart:

```env
API_KEY=my-custom-secret-key
```

---

## 🔍 Features Overview

| Feature | Interactive (menu) | Automatic (monitoring) | API |
|---------|-------------------|----------------------|-----|
| Docker containers | Start, stop, restart, status, policy | Per-item policy alerts | All actions + CRUD |
| Docker Compose stacks | Up, down, restart, pull, logs | -- | All actions + logs |
| Systemd services | Start, stop, restart, status, policy | Per-item policy alerts | All actions + CRUD |
| System info | On-demand overview | CPU, temp & disk alerts | On-demand |
| Security | Full overview on request | Brute force & ban alerts | Full overview |
| Server ping | On-demand check | State-change alerts | On-demand |
| Wake-on-LAN | Wake configured device | -- | Via HTTP |
| Container updates | Dry-run, update, rollback | -- | Via HTTP |
| Backups | Trigger, status, disk usage | -- | Via HTTP |
| Log viewer | Browse & download as .txt | -- | List & read tail |
| Custom commands | Execute any shell command | -- | Via HTTP |
| Custom scripts | Run configured scripts | -- | -- |
| Settings | Toggle features, thresholds, policies | -- | -- |

---

## 🌐 HTTP API

The API runs on `localhost:8120` -- not exposed to the internet. For remote access, expose it via [Cloudflare Tunnel](#-cloudflare-tunnel-setup). All endpoints (except `/api/health`) require the `X-API-Key` header.

```bash
# Health check (no auth)
curl http://localhost:8120/api/health

# Get container status
curl -H "X-API-Key: $KEY" http://localhost:8120/api/docker/status

# Add a container to monitoring
curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  http://localhost:8120/api/containers/add -d '{"name": "redis", "on_failure": "notify"}'

# Interactive Swagger docs
open http://localhost:8120/docs
```

See [`agent/ENDPOINTS.md`](agent/ENDPOINTS.md) for the complete endpoint reference with request/response examples.

### AI Agent Integration

The [`agent/`](agent/) directory contains a self-contained integration kit: skill prompts, endpoint schemas, workflow recipes, and multi-server configuration. See [`agent/README.md`](agent/README.md) for setup instructions.

### 🔒 Cloudflare Tunnel Setup

The API runs on localhost only. To access it remotely, add a route to your existing Cloudflare Tunnel.

**Step 1: Add the route**

If using a `cloudflared` config file, add an ingress rule:

```yaml
# /etc/cloudflared/config.yml
ingress:
  - hostname: api-myserver.example.com
    service: http://localhost:8120
  # ... your other routes ...
  - service: http_status:404
```

Then restart cloudflared:

```bash
docker restart cloudflared
# or: sudo systemctl restart cloudflared
```

If using the Cloudflare Tunnel dashboard:
1. Go to **Zero Trust** → **Networks** → **Tunnels**
2. Click your tunnel → **Configure**
3. Add a **Public Hostname**: subdomain `api-myserver`, service `http://localhost:8120`

**Step 2: Test it**

```bash
curl https://api-myserver.example.com/api/health
curl -H "X-API-Key: $KEY" https://api-myserver.example.com/api/docker/status
```

---

## 🤖 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/menu` | Show interactive menu |
| `/docker` | Docker container management |
| `/compose` | Docker Compose stack management |
| `/services` | Systemd service management |
| `/sysinfo` | System information |
| `/security` | Security overview |
| `/logs` | View log files |
| `/ping` | Ping configured servers |
| `/command` | Execute a shell command |
| `/scripts` | Run custom scripts |
| `/updates` | Container updates (dry-run, update, rollback) |
| `/backups` | Backup management |
| `/wakewol` | Wake-on-LAN |
| `/settings` | Manage features, thresholds, and policies |
| `/reboot` | Reboot server (with confirmation) |
| `/reload` | Reload config without restart |

---

## 🗂️ Project Structure

```
src/linux_server_bot/
    config.py              # YAML config + watchdog hot-reload + CRUD helpers
    bot/
        app.py             # Bot entrypoint
        menus.py           # Keyboard builder (hides unconfigured features)
        callbacks.py       # Central InlineKeyboard callback router
        handlers/          # One module per feature
    monitoring/
        app.py             # Monitoring scheduler
        checks/            # One module per check type
    api/
        server.py          # FastAPI app + uvicorn entrypoint
        auth.py            # API key authentication
        routes.py          # All REST endpoints (including CRUD for services/containers)
    shared/
        startup.py         # Setup wizard, API key generation, preflight checks
        shell.py           # Subprocess wrappers (auto nsenter in Docker)
        auth.py            # Authorization decorator
        telegram.py        # Messaging helpers (chunking, escaping)
        logging_setup.py   # Log rotation setup
        actions/           # Business logic shared by bot + API
```

---

## 🐛 Troubleshooting

**Bot not responding to commands**

```bash
docker compose ps                         # all 3 containers should be Up
docker compose logs bot --tail 20         # check for errors
grep SECRET_TOKEN .env                    # verify token is set
grep CHAT_ID .env                         # verify chat ID is set
```

**"Permission denied" for systemctl or host commands**

```bash
# Verify nsenter works from inside the container:
docker exec linux-server-bot nsenter -t 1 -m -- systemctl is-active docker
# Should print "active". If "Operation not permitted", check docker-compose.yml has:
#   privileged: true
#   pid: host
```

**Monitoring not sending alerts**

```bash
docker compose logs monitoring --tail 20
# Only services/containers listed in config.yaml are monitored.
# Check the failure policy is not set to 'ignore'.
```

**API returning 403 or not starting**

```bash
grep API_KEY .env                         # should NOT be "your-secret-api-key-here"
curl http://localhost:8120/api/health     # should return {"status": "healthy"}
docker compose logs api --tail 20
```

For more specific issues, check the logs in the `logs/` directory.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer

**USE AT YOUR OWN RISK**

This bot executes system commands and manages Docker containers and services. While designed with safety in mind:

- **Restrict access:** Only add trusted Telegram user IDs to `allowed_users`
- **Secure the API:** Use strong API keys and Cloudflare Tunnel for remote access
- **No guarantees:** We're not responsible for data loss or downtime

---

**Made with ❤️ by MadeByAdem**

If you find this bot useful, consider giving this repository a ⭐ on GitHub!

---

## 📚 Related Projects

- [linux-server-management-scripts](https://github.com/Made-By-Adem/linux-server-management-scripts) - Server setup, hardening, container updates & backup scripts
