# Deploying Simba Intelligence — Local Development

For local POC and development using Docker Desktop Kubernetes or kind.

---

## Chart versions

Find available versions at:
https://hub.docker.com/r/insightsoftware/simba-intelligence-chart/tags

Choose semantic versioning tags (e.g. `26.2.1`). Avoid `latest`, `main`, or `dev`.

---

## Values file

For local development, disable ingress and access via port-forwards + Caddy.

### PowerShell (Windows):
```powershell
New-Item -ItemType Directory -Force -Path C:\temp | Out-Null
@"
ingress:
  enabled: false
"@ | Out-File -Encoding utf8 C:\temp\simba-values.yaml
```

### Bash (macOS/Linux):
```bash
cat > /tmp/simba-values.yaml << 'EOF'
ingress:
  enabled: false
EOF
```

---

## Install

### Step 1: Dry run

PowerShell:
```powershell
helm install si oci://docker.io/insightsoftware/simba-intelligence-chart `
  --version <VERSION> `
  -f C:\temp\simba-values.yaml `
  --namespace simba-intel `
  --create-namespace `
  --dry-run --debug
```

Bash:
```bash
helm install si oci://docker.io/insightsoftware/simba-intelligence-chart \
  --version <VERSION> \
  -f /tmp/simba-values.yaml \
  --namespace simba-intel \
  --create-namespace \
  --dry-run --debug
```

Replace `<VERSION>` with the chosen chart version.

### Step 2: Install

Remove `--dry-run --debug` and run again.

Release name `si` means all resources are prefixed `si-` (e.g.
`si-simba-intelligence-chart`, `si-discovery-web`).

### Step 3: Wait for pods

```bash
kubectl -n simba-intel get pods -w
```

First install takes 5-10 minutes (image pull). Expected pods when healthy:

| Pod | Type | Ready state |
|---|---|---|
| `si-simba-intelligence-chart-*` | Deployment | 1/1 Running |
| `si-simba-intelligence-chart-worker-*` | Deployment | 1/1 Running |
| `si-simba-intelligence-chart-mcp-*` | Deployment | 1/1 Running |
| `si-simba-intelligence-chart-celery-beat-0` | StatefulSet | 1/1 Running |
| `si-discovery-web-0` | StatefulSet | 1/1 Running |
| `si-discovery-query-engine-0` | StatefulSet | 1/1 Running |
| `si-discovery-edc-postgresql-0` | StatefulSet | 1/1 Running |
| `si-logi-symphony-postgresql-0` | StatefulSet | 1/1 Running |
| `si-simba-intelligence-chart-redis-0` | StatefulSet | 1/1 Running |
| `si-consul-server-0` | StatefulSet | 1/1 Running |
| `si-reloader-*` | Deployment | 1/1 Running |
| `si-simba-intelligence-chart-dbm-<nnnn>-<nnn>-*` | Job | 0/1 Completed |
| `si-simba-intelligence-chart-init-<nnnn>-<nnn>-*` | Job | 0/1 Completed |

Corrected 2026-08-28 against the running 26.2.1 lab. Three rows in the table
above were wrong:

- The MCP pod is **1/1**, not 2/2. The nginx sidecar was removed in 26.2, so
  the deployment has one container. Proof:
  `kubectl -n simba-intel get pod -o jsonpath='{.status.containerStatuses[*].name}'`
  on the MCP pod returns the single name `simba-intelligence-chart-mcp`.
- The two Jobs are no longer named `db-migrate` and `initjob`. On this chart
  they render as `si-simba-intelligence-chart-dbm-2608-001` and
  `si-simba-intelligence-chart-init-2608-001`. The suffix is generated per
  chart build, so match on the `dbm-` and `init-` stems, never on the old
  names. Proof: `helm -n simba-intel get manifest si | grep -A2 '^kind: Job'`.
- **The Jobs disappear.** They set `ttlSecondsAfterFinished: 86400` (dbm) and
  `3600` (init), so Kubernetes garbage-collects them one day and one hour
  after they succeed. `kubectl -n simba-intel get jobs` on a healthy install
  older than a day returns `No resources found`. That is success, not
  failure. Do not wait for a Job that has already been collected. Proof:
  `helm -n simba-intel get manifest si | grep ttlSecondsAfterFinished`.

### Step 4: Verify services

```bash
kubectl -n simba-intel get svc
```

Confirm `si-simba-intelligence-chart` port 5050 and `si-discovery-web` port 9050.

---

## Next steps

1. Set up local access — see `local-access.md`
2. Configure LLM provider — see `llm-config.md`
3. Create data connections and sources — see `post-install.md`
