# Common Workflows

Practical workflows for managing Linux servers via the API. All examples use `curl` -- adapt to your agent's HTTP client.

Replace `$URL` with your server's base URL (e.g., `https://api-homelab.example.com/api`) and `$KEY` with your API key.

---

## 1. Daily Health Check

Check that the server, all containers, and all services are healthy.

```bash
# 1. Verify API is reachable
curl -s $URL/health

# 2. Check system resources
curl -s -H "X-API-Key: $KEY" $URL/sysinfo/cpu
curl -s -H "X-API-Key: $KEY" $URL/sysinfo/memory
curl -s -H "X-API-Key: $KEY" $URL/sysinfo/disk
curl -s -H "X-API-Key: $KEY" $URL/sysinfo/temperature

# 3. Check container statuses
curl -s -H "X-API-Key: $KEY" $URL/docker/status

# 4. Check service statuses
curl -s -H "X-API-Key: $KEY" $URL/services/status

# 5. Check security
curl -s -H "X-API-Key: $KEY" $URL/security/failed-logins
curl -s -H "X-API-Key: $KEY" $URL/security/fail2ban
```

**Decision tree:**
- CPU > 80% → check top processes via `/api/command` with `{"command": "ps aux --sort=-%cpu | head -15"}`
- Disk > 90% → run Docker cleanup via `/api/docker/cleanup`
- Container down → restart via `/api/docker/restart/{name}`
- Service down → restart via `/api/services/restart/{name}`
- Many failed logins → verify Fail2ban is active via `/api/security/fail2ban`

---

## 2. Restart a Failing Container

```bash
# 1. Check container status
curl -s -H "X-API-Key: $KEY" $URL/docker/status

# 2. Restart the failing container
curl -s -X POST -H "X-API-Key: $KEY" $URL/docker/restart/nginx

# 3. Verify it's running again
curl -s -H "X-API-Key: $KEY" $URL/docker/status
```

---

## 3. Updates -- System Packages + Containers (Safe)

In the Telegram bot, both are under one "Updates + Containers" button. Via API, use the separate endpoints below.

### System packages (apt)

```bash
# 1. Check what's available -- does NOT install anything
curl -s -X POST -H "X-API-Key: $KEY" $URL/system-updates/check
# Response includes: count, packages list, rkhunter (bool)

# 2. Review the count and package list before proceeding

# 3. If the updates look good, apply them
curl -s -X POST -H "X-API-Key: $KEY" $URL/system-updates/apply
# Runs: apt-get upgrade -y
# If rkhunter is installed: also runs rkhunter --propupd

# 4. Verify system is still healthy
curl -s -H "X-API-Key: $KEY" $URL/sysinfo
curl -s -H "X-API-Key: $KEY" $URL/services/status
```

### Containers (via script)

```bash
# 1. Dry-run first -- preview what would change
curl -s -X POST -H "X-API-Key: $KEY" $URL/updates/dry-run

# 2. If dry-run looks good, apply the updates
curl -s -X POST -H "X-API-Key: $KEY" $URL/updates/run

# 3. Verify containers are healthy after update
curl -s -H "X-API-Key: $KEY" $URL/docker/status

# 4. If something is broken, rollback
curl -s -X POST -H "X-API-Key: $KEY" $URL/updates/rollback
```

**Decision tree:**
- System: 0 packages → skip; security updates only → safe to apply; major version bumps → review carefully
- Containers: dry-run shows no changes → skip; dry-run shows updates → apply and verify
- After applying either → check services and containers are still running

---

## 4. Security Audit

```bash
# 1. Full security overview
curl -s -H "X-API-Key: $KEY" $URL/security

# 2. Check for available system updates
curl -s -H "X-API-Key: $KEY" $URL/security/updates

# 3. Review firewall rules
curl -s -H "X-API-Key: $KEY" $URL/security/ufw

# 4. Check for brute force attempts
curl -s -H "X-API-Key: $KEY" $URL/security/failed-logins

# 5. Review Fail2ban bans
curl -s -H "X-API-Key: $KEY" $URL/security/fail2ban

# 6. Check active SSH sessions
curl -s -H "X-API-Key: $KEY" $URL/security/ssh
```

**Red flags to act on:**
- Many failed logins from a single IP → Fail2ban should auto-ban; if not, check its status
- UFW disabled → alert the server owner
- Available security updates → schedule update window
- Unknown SSH sessions → investigate immediately

---

## 5. Compose Stack Management

```bash
# 1. Check all stack statuses
curl -s -H "X-API-Key: $KEY" $URL/compose/status

# 2. View logs of a specific stack
curl -s -H "X-API-Key: $KEY" "$URL/compose/logs/media-stack?tail=100"

# 3. Pull latest images and recreate
curl -s -X POST -H "X-API-Key: $KEY" $URL/compose/pull/media-stack

# 4. Restart a stack
curl -s -X POST -H "X-API-Key: $KEY" $URL/compose/restart/monitoring
```

---

## 6. Backup and Verify

```bash
# 1. Check current backup status
curl -s -H "X-API-Key: $KEY" $URL/backups/status

# 2. Check backup disk usage
curl -s -H "X-API-Key: $KEY" $URL/backups/size

# 3. Trigger a new backup
curl -s -X POST -H "X-API-Key: $KEY" $URL/backups/trigger

# 3b. Trigger a backup for a specific target (if configured in scripts.backup.targets)
curl -s -X POST -H "X-API-Key: $KEY" "$URL/backups/trigger?target=ac3"
```

---

## 7. Investigate High Resource Usage

```bash
# 1. Check CPU
curl -s -H "X-API-Key: $KEY" $URL/sysinfo/cpu

# 2. If high, check top processes
curl -s -X POST -H "X-API-Key: $KEY" $URL/command \
  -H "Content-Type: application/json" \
  -d '{"command": "ps aux --sort=-%cpu | head -15"}'

# 3. Check memory
curl -s -H "X-API-Key: $KEY" $URL/sysinfo/memory

# 4. If memory is full, check what's using it
curl -s -X POST -H "X-API-Key: $KEY" $URL/command \
  -H "Content-Type: application/json" \
  -d '{"command": "ps aux --sort=-%mem | head -15"}'

# 5. Check disk
curl -s -H "X-API-Key: $KEY" $URL/sysinfo/disk

# 6. If disk is full, check largest directories
curl -s -X POST -H "X-API-Key: $KEY" $URL/command \
  -H "Content-Type: application/json" \
  -d '{"command": "du -h --max-depth=1 / 2>/dev/null | sort -rh | head -15"}'
```

---

## 8. Log Investigation

```bash
# 1. List available log files
curl -s -H "X-API-Key: $KEY" $URL/logs

# 2. Read the last 100 lines of a specific log (use index from step 1)
curl -s -H "X-API-Key: $KEY" "$URL/logs/0?tail=100"

# 3. Check auth.log for brute force patterns
curl -s -H "X-API-Key: $KEY" "$URL/logs/0?tail=200"
# Parse the content field for "Failed password" lines
```

---

## 9. Multi-Server Overview

When managing multiple servers, run the health check workflow against each server in parallel:

```bash
SERVERS=("https://api-homelab.example.com/api" "https://api-vps.example.com/api")
KEYS=("key1" "key2")

for i in "${!SERVERS[@]}"; do
  echo "=== Server $i ==="
  curl -s -H "X-API-Key: ${KEYS[$i]}" ${SERVERS[$i]}/sysinfo/cpu
  curl -s -H "X-API-Key: ${KEYS[$i]}" ${SERVERS[$i]}/docker/status
  curl -s -H "X-API-Key: ${KEYS[$i]}" ${SERVERS[$i]}/security/failed-logins
done
```

---

## 10. AI Agent Autonomous Loop

Example of how an AI agent can autonomously monitor and remediate issues. Run periodically (e.g., every 5 minutes).

```
1. GET /api/health                → if unreachable, alert and stop

2. GET /api/sysinfo/cpu           → if cpu_percent > 80:
   POST /api/command              → {"command": "ps aux --sort=-%cpu | head -10"}
                                    → report top processes

3. GET /api/sysinfo/disk          → if any partition > 90%:
   POST /api/docker/cleanup       → free up Docker space
   GET /api/sysinfo/disk          → verify improvement

4. GET /api/docker/status         → for each container where running == false:
   POST /api/docker/restart/{name}→ restart it
   GET /api/docker/status         → verify it came back up

5. GET /api/services/status       → for each service where active == false:
   POST /api/services/restart/{name} → restart it

6. GET /api/security/failed-logins→ if found == true:
   GET /api/security/fail2ban     → verify fail2ban is active
   GET /api/logs/0?tail=50        → check auth.log for patterns

7. POST /api/system-updates/check → if count > 0:
                                    → report available updates (do NOT auto-apply)

8. GET /api/backups/status        → if last backup > 24h ago:
   POST /api/backups/trigger      → start backup
```

## 11. Threshold Management

View and adjust monitoring thresholds dynamically.

```bash
# 1. Check current thresholds
curl -s -H "X-API-Key: $KEY" $URL/monitoring/thresholds

# 2. Raise CPU threshold if legitimate workload causes frequent alerts
curl -s -X PUT -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  $URL/monitoring/thresholds -d '{"key": "cpu_percent", "value": 90}'

# 3. Lower disk threshold for early warning
curl -s -X PUT -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  $URL/monitoring/thresholds -d '{"key": "storage_percent", "value": 80}'

# 4. Increase recheck delay (seconds to wait before second verification)
curl -s -X PUT -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  $URL/monitoring/thresholds -d '{"key": "recheck_delay_seconds", "value": 10}'

# 5. Verify new thresholds
curl -s -H "X-API-Key: $KEY" $URL/monitoring/thresholds
```

---

**Key principles for AI agents:**
- Always check status **before and after** an action to verify the result
- Use `/api/command` as a fallback for diagnostics not covered by dedicated endpoints
- Use `/api/logs` to investigate root causes (check auth.log, syslog, fail2ban.log)
- Never call `/api/reboot` without explicit human approval
