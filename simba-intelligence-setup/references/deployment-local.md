# Deploying Simba Intelligence — Local Development

For local POC and development using Docker Desktop Kubernetes or kind.

---

## Chart versions

Find available versions at:
https://hub.docker.com/r/insightsoftware/simba-intelligence-chart/tags

Choose semantic versioning tags (e.g. `25.4.0`). Avoid `latest`, `main`, or `dev`.

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
| `si-simba-intelligence-chart-mcp-*` | Deployment | 2/2 Running |
| `si-simba-intelligence-chart-celery-beat-0` | StatefulSet | 1/1 Running |
| `si-discovery-web-0` | StatefulSet | 1/1 Running |
| `si-discovery-query-engine-0` | StatefulSet | 1/1 Running |
| `si-discovery-edc-postgresql-0` | StatefulSet | 1/1 Running |
| `si-logi-symphony-postgresql-0` | StatefulSet | 1/1 Running |
| `si-simba-intelligence-chart-redis-0` | StatefulSet | 1/1 Running |
| `si-consul-server-0` | StatefulSet | 1/1 Running |
| `si-reloader-*` | Deployment | 1/1 Running |
| `si-simba-intelligence-chart-db-migrate-*` | Job | 0/1 Completed |
| `si-simba-intelligence-chart-initjob-*` | Job | 0/1 Completed |

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
