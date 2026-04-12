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

## 3. Update Containers (Safe)

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

## 8. Multi-Server Overview

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
