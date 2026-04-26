# Agent Integration Guide

This directory contains everything an AI agent needs to manage Linux servers via the Linux Server Bot API.

---

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | API skill definition -- load this as a system prompt or tool description for your agent |
| `ENDPOINTS.md` | Complete endpoint reference with request/response JSON schemas |
| `workflows.md` | Step-by-step workflows with curl examples for common server management tasks |
| `.env.example` | Environment variables template for multi-server configuration |

---

## Quick Setup

### 1. Deploy the API on your server(s)

Follow the main [README](../README.md) to deploy the bot + API via Docker Compose. Ensure the API section is enabled in `config/config.yaml`:

```yaml
api:
  enabled: true
  port: 8120
  api_key: ${API_KEY}
```

### 2. Expose the API (optional, for remote access)

For remote agent access, expose the API via [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/):

```yaml
# /etc/cloudflared/config.yml
ingress:
  - hostname: api-myserver.example.com
    service: http://localhost:8120
```

### 3. Configure the agent

Copy `.env.example` and fill in your server details:

```bash
cp .env.example .env
# Edit with your server URLs and API keys
```

### 4. Load the skill

Give your AI agent the contents of `SKILL.md` as context. This tells the agent what endpoints are available and how to authenticate.

**Claude Code**: Place `SKILL.md` in your project root or reference it in your system prompt.

**OpenAI / custom agents**: Include the skill content in your system message or function definitions.

**MCP (Model Context Protocol)**: Use the endpoints as HTTP tool definitions -- see the Swagger docs at `/docs` on your server for the OpenAPI spec.

---

## How It Works

```
AI Agent
  │
  ├── Server 1: https://api-homelab.example.com/api  (X-API-Key: key1)
  ├── Server 2: https://api-vps.example.com/api       (X-API-Key: key2)
  └── Server 3: http://192.168.1.100:8120/api          (X-API-Key: key3)
         │
         ▼
   Linux Server Bot API (FastAPI)
         │
         ▼
   shared/actions/ layer
         │
         ├── Docker Socket         → Containers
         ├── nsenter + systemctl   → Systemd Services
         ├── nsenter + shell       → Updates / Backups / Commands
         └── netcat                → Server Pings
```

Each server runs its own API instance. The agent authenticates with each server independently using its API key.

---

## OpenAPI / Swagger

Every server exposes auto-generated API documentation:

| URL | Format |
|-----|--------|
| `/docs` | Swagger UI (interactive) |
| `/redoc` | ReDoc (readable) |
| `/openapi.json` | OpenAPI 3.0 spec (machine-readable) |

You can use `/openapi.json` to auto-generate tool definitions for your agent framework.

---

## Security Considerations

- **API keys** are auto-generated on first startup (check `.env` on the server); should be unique per server
- **Cloudflare Tunnel** is recommended over opening ports -- no firewall changes needed
- **The `/api/command` endpoint** executes arbitrary shell commands -- restrict access carefully
- **The `/api/reboot` endpoint** requires explicit `{"confirm": true}` as a safeguard
- Use **Cloudflare Access** or similar zero-trust policies for additional protection
