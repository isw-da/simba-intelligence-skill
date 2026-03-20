# Prerequisites

This guide covers setting up a machine from scratch to be ready for a Simba
Intelligence deployment. Walk the user through each section, confirming
success before moving on.

---

## Required tools

| Tool | Minimum version | Purpose |
|---|---|---|
| Docker Desktop (local) or container runtime | Latest stable | Container execution |
| Kubernetes cluster | 1.24+ | Orchestration |
| Helm | 3.17+ | Package management |
| kubectl | Matching cluster version | Cluster management |
| LLM provider account | — | AI capabilities (Vertex AI, Azure OpenAI, Bedrock, or OpenAI) |

---

## Docker Desktop (local development only)

Cloud and on-prem deployments do not need Docker Desktop — skip to
"Kubernetes cluster" below.

### Windows

1. Download: https://www.docker.com/products/docker-desktop/
2. Run the installer, accept defaults, restart if prompted
3. Open Docker Desktop, wait for "Engine running" in the bottom-left

```powershell
docker --version
docker info | Select-Object -First 3
```

### macOS

1. Download: https://www.docker.com/products/docker-desktop/
2. Drag to Applications, open, grant permissions
3. Wait for the whale icon to stop animating

```bash
docker --version
docker info | head -3
```

---

## Kubernetes cluster

### Option A: Docker Desktop built-in Kubernetes (recommended for local POC)

1. Docker Desktop → Settings → Kubernetes → Enable Kubernetes
2. Apply & Restart — first enable takes several minutes
3. Wait for "Kubernetes running" in green

```powershell
kubectl get nodes
```

Expected: `docker-desktop` with `STATUS = Ready`.

### Option B: kind (alternative for local development, macOS)

```bash
brew install kind
kind create cluster --name simba-intel-lab
kubectl get nodes
```

### Option C: Cloud-managed Kubernetes

- **EKS**: `eksctl create cluster` or AWS Console
- **AKS**: `az aks create` or Azure Portal
- **GKE**: `gcloud container clusters create` or GCP Console

See `deployment-cloud.md` for cloud-specific prerequisites.

### Option D: On-premises Kubernetes

Any conformant Kubernetes 1.24+ distribution (Rancher, OpenShift, Tanzu, kubeadm).
See `deployment-onprem.md`.

---

## Helm

### Windows
```powershell
winget install Helm.Helm
# Close and reopen PowerShell
```

### macOS
```bash
brew install helm
```

### Linux
```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

### Verify
```bash
helm version
```

Must show 3.17+.

---

## kubectl

Docker Desktop installs kubectl automatically. For other environments:

- https://kubernetes.io/docs/tasks/tools/

Verify:
```bash
kubectl version --client
kubectl get nodes
```

---

## Verification checklist

Run all of these. All must pass before proceeding.

```bash
docker info | head -1          # Docker running
kubectl get nodes              # Cluster ready, node STATUS = Ready
helm version                   # Helm 3.17+
```

---

## Common issues

| Problem | Fix |
|---|---|
| "docker: command not found" | Install Docker Desktop, reopen terminal |
| "kubectl: command not found" | Reopen terminal after Docker Desktop install, or install kubectl separately |
| "helm: command not found" | Reopen terminal after Helm install |
| Node shows "NotReady" | K8s still starting — wait 1-2 minutes |
| "Unable to connect to the server" | Docker Desktop not running or K8s not enabled |
