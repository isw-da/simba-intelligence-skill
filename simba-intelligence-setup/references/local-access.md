# Local Access — Port-Forwards and Caddy Reverse Proxy

For local development and POC environments where no ingress controller or
DNS is available. This approach works on both Docker Desktop Kubernetes
(Windows, macOS) and kind clusters.

---

## Why this is needed

Simba Intelligence has two web components that must be reachable from a
single URL. Without an ingress controller, these services are only
accessible inside the cluster. Port-forwarding exposes them to localhost,
and a Caddy reverse proxy combines them into one URL.

This is the expected approach for local environments — it is not a workaround.

---

## Step 1: Check for port collisions

CRITICAL: Do this before starting anything. Other containers commonly
hold ports 8080 and 8081.

### PowerShell (Windows):
```powershell
netstat -ano | findstr ":8080 :8081 :8082" | findstr LISTENING
```

### Bash (macOS/Linux):
```bash
lsof -nP -iTCP:8080 -sTCP:LISTEN
lsof -nP -iTCP:8081 -sTCP:LISTEN
lsof -nP -iTCP:8082 -sTCP:LISTEN
```

If ports are occupied, identify the process:
```bash
docker ps    # Check if it is a container
```

Stop the specific container:
```bash
docker stop <container-id>
```

WARNING: Do not kill processes by PID without identifying them first. If the
PID belongs to Docker Desktop, killing it will crash the Kubernetes cluster.

---

## Step 2: Start port-forwards

Each runs in its own terminal window. If the terminal closes, the
port-forward dies and the reverse proxy returns 502.

Always use the full `LOCAL:REMOTE` mapping syntax.

### Terminal 1 — Main application:
```powershell
kubectl -n simba-intel port-forward svc/si-simba-intelligence-chart 8082:5050
```
Expected: `Forwarding from 127.0.0.1:8082 -> 5050`

### Terminal 2 — Discovery web:
```powershell
kubectl -n simba-intel port-forward svc/si-discovery-web 8081:9050
```
Expected: `Forwarding from 127.0.0.1:8081 -> 8080`
(The `-> 8080` is the container port behind the service. This is correct.)

---

## Step 3: Create and start Caddy

### Save the Caddyfile

PowerShell (Windows):
```powershell
@"
:8080 {
  @discovery path /discovery/*
  reverse_proxy @discovery host.docker.internal:8081

  reverse_proxy host.docker.internal:8082
}
"@ | Out-File -Encoding utf8 C:\temp\Caddyfile
```

Bash (macOS/Linux):
```bash
cat > /tmp/Caddyfile << 'EOF'
:8080 {
  @discovery path /discovery/*
  reverse_proxy @discovery host.docker.internal:8081

  reverse_proxy host.docker.internal:8082
}
EOF
```

### Terminal 3 — Start Caddy:

PowerShell (Windows):
```powershell
docker run --rm -p 8080:8080 -v C:\temp\Caddyfile:/etc/caddy/Caddyfile caddy:2
```

Bash (macOS/Linux):
```bash
docker run --rm -p 8080:8080 -v /tmp/Caddyfile:/etc/caddy/Caddyfile caddy:2
```

A formatting warning in the Caddy logs is harmless.

---

## Step 4: Verify

### PowerShell:
```powershell
curl.exe -si http://localhost:8080/ | Select-Object -First 5
curl.exe -si http://localhost:8080/discovery/api/user | Select-Object -First 10
```

### Bash:
```bash
curl -si http://localhost:8080/ | head -5
curl -si http://localhost:8080/discovery/api/user | head -10
```

Expected:
- First request: HTML (SI app index page)
- Second request: **401 JSON** — this means Discovery is reachable and
  working. It returns 401 because it expects auth from the main app session.

If Discovery returns HTML instead of JSON, requests are hitting the main
app SPA, not Discovery. Check the Caddyfile and the Discovery port-forward.

Open http://localhost:8080 in a browser.

---

## Key rules

1. Service port is **5050**, not 80. Always use `8082:5050`.
2. Always use full mapping: `8082:5050`, not just `8082`.
3. 401 from Discovery is normal. Access it through the main app.
4. HTML from `/discovery/api/*` means routing is broken.
5. "Stuck on login" is a routing problem, not a credentials problem.
6. All three terminals must stay open.
7. Check for port collisions first. Do not kill PIDs blindly.
8. On Windows, use `curl.exe` (not `curl`, which is a PowerShell alias).
9. On Windows, Caddyfile path is `C:\temp\Caddyfile`.
