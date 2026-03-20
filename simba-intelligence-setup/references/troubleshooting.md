# Troubleshooting Simba Intelligence

---

## Quick diagnostics

Run these first to assess overall health:

```bash
kubectl -n simba-intel get pods -o wide
kubectl -n simba-intel get svc
kubectl -n simba-intel get events --sort-by=.lastTimestamp | tail -40
```

---

## Pod reference

### Deployments (restart with `kubectl rollout restart deploy/<name>`):
- `si-simba-intelligence-chart` — main web application
- `si-simba-intelligence-chart-worker` — Celery task worker
- `si-simba-intelligence-chart-mcp` — MCP server (2 containers)
- `si-reloader` — configuration reloader

### StatefulSets (restart by deleting the pod — it recreates):
- `si-discovery-web-0` — Discovery UI
- `si-discovery-query-engine-0` — query engine
- `si-discovery-edc-postgresql-0` — Discovery database
- `si-logi-symphony-postgresql-0` — main database
- `si-simba-intelligence-chart-redis-0` — cache
- `si-consul-server-0` — service discovery
- `si-simba-intelligence-chart-celery-beat-0` — task scheduler

### Jobs (one-off, should show Completed):
- `si-simba-intelligence-chart-db-migrate-*` — database migration
- `si-simba-intelligence-chart-initjob-*` — initialisation

---

## Checking logs

```bash
kubectl -n simba-intel logs deploy/si-simba-intelligence-chart --tail=200
kubectl -n simba-intel logs deploy/si-simba-intelligence-chart-mcp --all-containers --tail=200
kubectl -n simba-intel logs deploy/si-simba-intelligence-chart-worker --tail=200
kubectl -n simba-intel logs sts/si-discovery-web --tail=200
kubectl -n simba-intel logs sts/si-logi-symphony-postgresql --tail=100
```

### Log patterns to search for
- `401` or `403` loops — authentication or permission cycling
- `connection refused` — a downstream service is not running
- `migration` or `schema` errors — database initialisation problem
- `timeout` — LLM provider or database latency

---

## Symptom: Port already in use (local setup)

**Cause:** Another container or process holds port 8080, 8081, or 8082.

### Diagnose:
```powershell
# Windows
netstat -ano | findstr ":8080 :8081 :8082" | findstr LISTENING

# macOS/Linux
lsof -nP -iTCP:8080 -sTCP:LISTEN
```

### Fix:
1. Check if it is a Docker container: `docker ps`
2. Stop the specific container: `docker stop <container-id>`

WARNING: Do not run `taskkill /PID <n> /F` on Windows without first
identifying the process. If the PID belongs to Docker Desktop, killing it
crashes the Kubernetes cluster and requires a full Docker Desktop restart.

---

## Symptom: Docker CLI "daemon not running"

**Cause:** Docker Desktop GUI may appear running while the engine is not
connected to the CLI.

### Fix:
1. Quit Docker Desktop fully (right-click system tray icon → Quit)
2. Wait 10 seconds
3. Reopen Docker Desktop
4. Wait for both "Engine running" and "Kubernetes running" in green
5. Then retry: `docker info` and `kubectl get nodes`

---

## Symptom: kubectl "connection refused" or "unable to connect"

**Cause:** Kubernetes is not running.

### Fix:
1. Check Docker Desktop is open and shows "Kubernetes running"
2. If not, enable Kubernetes in Docker Desktop Settings → Kubernetes
3. For kind: `kind get clusters` — if empty, the cluster was deleted

---

## Symptom: Caddy returns 502

**Cause:** The port-forward behind Caddy is dead.

### Diagnose:
```bash
# Are the port-forwards still listening?
curl -si http://localhost:8082/api/v1/healthz | head -5
curl -si http://localhost:8081/discovery/api/user | head -5
```

### Fix:
Restart the dead port-forward in a new terminal. If pods are down, check
pod status first.

---

## Symptom: Login loop / stuck on login

**Cause:** Almost always a routing problem. Discovery requests are hitting
the main app SPA instead of the Discovery service.

### Diagnose:
```bash
curl -si http://localhost:8080/discovery/api/user | head -10
```

- 401 JSON → routing is correct, issue is elsewhere
- HTML → requests are hitting the main app, not Discovery

### Fix:
- **Local setup**: Check Caddyfile routes `/discovery/*` to port 8081.
  Confirm the Discovery port-forward is alive.
- **Production ingress**: Check ingress configuration handles `/discovery/*`
  path routing correctly. The Helm chart should configure this automatically
  when `ingress.enabled: true`.

---

## Symptom: "No LLM Configuration Found"

No AI provider configured. Navigate to `/llm-configuration` and set up a
provider. See `llm-config.md`.

---

## Symptom: "No Data Connections Available"

No database connections created. Navigate to Data Connections in the UI.

---

## Symptom: Data Agent fails

Check in order:
1. Is LLM configured? (`/llm-configuration` — both Chat and Embeddings active?)
2. Is the data connection healthy? (Test Connection in Data Connections page)
3. Check main app logs for detailed error
4. Check LLM provider dashboard for quota or rate limit issues

---

## Symptom: Pods stuck in ImagePullBackOff

**Cause:** Cannot pull container images.

### Diagnose:
```bash
kubectl -n simba-intel describe pod <pod-name>
# Look at Events section for the exact image path it is trying to pull
```

### Common causes:

**No internet access:** Check connectivity from cluster nodes to Docker Hub.
For air-gapped environments, verify images are in the internal registry with
correct tags.

**Docker Hub rate limits:** Anonymous pulls are throttled. Use authenticated
pulls or mirror images to an internal registry.

**Known issue — missing fully qualified image paths (OKE and newer K8s):**

Some Helm chart image references do not include the full registry prefix
(`docker.io/`). Older Kubernetes versions defaulted to `docker.io`
automatically, but newer Kubernetes versions (Oracle Kubernetes Engine / OKE
first, others will follow) no longer do this.

Symptoms: pods fail with `ImagePullBackOff` and the Events section shows an
image path without a registry prefix (e.g. `insightsoftware/zoomdata-web`
instead of `docker.io/insightsoftware/zoomdata-web`).

This affects both the SI chart and the Composer/Discovery subcharts.
Engineering is working on fully qualified paths across all images — expected
within the 26.1 release lifecycle.

**Workaround until the chart is fixed:**

1. Deploy the chart normally (it will fail on affected pods)
2. Identify which pods have the wrong image path:
   ```bash
   kubectl -n simba-intel get pods | grep ImagePullBackOff
   kubectl -n simba-intel describe pod <pod-name> | grep "Image:"
   ```
3. For Deployments, patch the image with the full registry prefix:
   ```bash
   kubectl -n simba-intel set image deployment/<deploy-name> \
     <container-name>=docker.io/<original-image-path>
   ```
4. For StatefulSets, edit the stateful set directly:
   ```bash
   kubectl -n simba-intel edit sts/<statefulset-name>
   # Add docker.io/ prefix to the image field
   ```
5. Affected pods will restart automatically with the corrected image path

Note: some images (e.g. the wait-console init container) are pulled within
the container itself, not from the pod spec. These require editing the
StatefulSet after initial deployment — they cannot be overridden via Helm
values alone.

**Environments affected so far:** Oracle Kubernetes Engine (OKE). EKS, AKS,
and GKE have not enforced this yet but are expected to in future K8s versions.

---

## Symptom: Pods stuck in CrashLoopBackOff

**Cause:** Application error during startup.

```bash
kubectl -n simba-intel logs <pod-name> --tail=200
kubectl -n simba-intel describe pod <pod-name>
```

Common causes: database not ready, migration failed, misconfigured values.

---

## Symptom: Service port error "does not have a service port 8082"

Wrong port-forward syntax. Must include the full mapping:

```bash
# WRONG:
kubectl -n simba-intel port-forward svc/si-simba-intelligence-chart 8082

# CORRECT:
kubectl -n simba-intel port-forward svc/si-simba-intelligence-chart 8082:5050
```

---

## Health check endpoints

| Endpoint | Service port | Expected | Meaning |
|---|---|---|---|
| `GET /api/v1/healthz` | 5050 (local: 8082) | 200 JSON | Main app healthy |
| `GET /discovery/api/user` | 9050 (local: 8081) | 401 JSON | Discovery reachable |

---

## Restart runbook (local environments)

After laptop sleep or Docker Desktop restart:

### PowerShell (Windows):
```powershell
# 1. Confirm Docker and K8s are running
docker info | Select-Object -First 1
kubectl get nodes

# 2. Check pods
kubectl -n simba-intel get pods

# 3. If pods are unhealthy, restart them
kubectl -n simba-intel rollout restart deploy/si-simba-intelligence-chart
kubectl -n simba-intel rollout restart deploy/si-simba-intelligence-chart-mcp
kubectl -n simba-intel rollout restart deploy/si-simba-intelligence-chart-worker
kubectl -n simba-intel delete pod si-discovery-web-0
kubectl -n simba-intel wait --for=condition=ready pod --all --timeout=300s

# 4. Check for port collisions
netstat -ano | findstr ":8080 :8081 :8082" | findstr LISTENING

# 5. Start port-forwards (separate terminals)
kubectl -n simba-intel port-forward svc/si-simba-intelligence-chart 8082:5050
kubectl -n simba-intel port-forward svc/si-discovery-web 8081:9050

# 6. Start Caddy
docker run --rm -p 8080:8080 -v C:\temp\Caddyfile:/etc/caddy/Caddyfile caddy:2
```

### Bash (macOS/Linux):
```bash
docker info > /dev/null 2>&1 && echo "Docker OK" || echo "Start Docker Desktop"
kubectl get nodes
kubectl -n simba-intel get pods
lsof -nP -iTCP:8080 -sTCP:LISTEN
lsof -nP -iTCP:8081 -sTCP:LISTEN
kubectl -n simba-intel port-forward svc/si-simba-intelligence-chart 8082:5050
kubectl -n simba-intel port-forward svc/si-discovery-web 8081:9050
docker run --rm -p 8080:8080 -v /tmp/Caddyfile:/etc/caddy/Caddyfile caddy:2
```
