# Teardown and Fresh Install

---

## Before tearing down

Save current configuration while the cluster is alive:

```bash
kubectl config current-context           # Identify cluster type
helm list --namespace simba-intel        # Release name and chart version
helm get values si --namespace simba-intel  # Current values
```

Keep the values output — you need it for reinstall.

---

## Step 1: Stop dependent processes

Close port-forward terminals and stop Caddy:

```bash
docker ps -q --filter ancestor=caddy:2 | xargs -r docker stop   # macOS/Linux
```

```powershell
docker ps -q --filter ancestor=caddy:2 | ForEach-Object { docker stop $_ }  # Windows
```

---

## Step 2: Uninstall Helm release

```bash
helm uninstall si --namespace simba-intel
```

---

## Step 3: Delete namespace

Removes all PVCs, secrets, configmaps, and leftover resources:

```bash
kubectl delete namespace simba-intel
```

Confirm:
```bash
kubectl get namespaces
```

---

## Step 4: Cluster reset (optional — for cleanest slate)

### Docker Desktop Kubernetes

1. Open Docker Desktop → Settings → Kubernetes
2. Click **"Reset Kubernetes Cluster"**
3. Wait for "Kubernetes running" in green
4. Verify: `kubectl get nodes`

### kind

```bash
kind delete cluster --name <cluster-name>
kind create cluster --name <cluster-name>
kubectl get nodes
```

### Cloud / on-prem

Deleting the namespace (Step 3) is sufficient. No cluster reset needed
unless there are other issues.

---

## Step 5: Clean up Docker resources (optional)

```bash
docker volume prune -f
docker network prune -f
```

---

## Step 6: Reinstall

Follow the appropriate deployment guide:
- Local: `deployment-local.md`
- Cloud: `deployment-cloud.md`
- On-prem: `deployment-onprem.md`
- Air-gapped: `deployment-airgapped.md`

Quick local reinstall:

```bash
helm install si oci://docker.io/insightsoftware/simba-intelligence-chart \
  --version <VERSION> \
  -f simba-values.yaml \
  --namespace simba-intel \
  --create-namespace
```

Then set up access (`local-access.md` or `production-ingress.md`) and
reconfigure the LLM provider (`llm-config.md`).
