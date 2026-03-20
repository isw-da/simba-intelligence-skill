# Deploying Simba Intelligence — Cloud Kubernetes

Covers Amazon EKS, Azure AKS, and Google GKE. The Helm chart is the same
across all cloud providers — the differences are in cluster setup, ingress
controller, IAM, and networking.

---

## Chart versions

Find available versions at:
https://hub.docker.com/r/insightsoftware/simba-intelligence-chart/tags

---

## Common values (all cloud providers)

Production deployments should enable ingress with TLS. See
`production-ingress.md` for full ingress configuration.

Minimal production values file:

```yaml
ingress:
  appendToPath: ""
  trimTrailingSlash: true
  enabled: true
  className: "<INGRESS_CLASS>"     # nginx, alb, traefik — see provider section
  annotations: {}                   # provider-specific annotations below
  hosts:
    - host: "simba.yourdomain.com"
      paths:
        - path: /
          pathType: ImplementationSpecific
```

---

## Amazon EKS

EKS has significantly more setup than AKS or GKE (storage driver, IAM,
OIDC provider). See the dedicated reference: `deployment-eks.md`.

That reference covers: eksctl cluster creation, EBS CSI driver setup, IAM
policies and OIDC, StorageClass configuration, Traefik ingress with
LoadBalancer, EDC connector driver uploads, and teardown.

---

## Azure AKS

### Prerequisites

- AKS cluster running Kubernetes 1.24+
- `kubectl` configured (`az aks get-credentials --name <cluster> --resource-group <rg>`)
- Helm 3.17+
- NGINX Ingress Controller installed (`helm install ingress-nginx ingress-nginx/ingress-nginx`)
- ACR access or outbound internet for Docker Hub

### Azure subscription gotchas

These are common blockers on new or trial Azure subscriptions. Address them
before creating the cluster.

**Container Service not registered:**
New subscriptions may not have the Kubernetes resource provider enabled:
```bash
az provider register --namespace Microsoft.ContainerService
az provider show --namespace Microsoft.ContainerService --query "registrationState" -o tsv
# Wait until it returns "Registered" (1-2 minutes)
```

**Free trial quota locks:**
Azure free trial subscriptions lock quota increase requests. If the pencil
icon is greyed out on the Quotas page, the subscription must be upgraded
to Pay-As-You-Go first. Credits carry over — the upgrade itself costs nothing.

**Two levels of vCPU quota:**
Azure enforces BOTH a Total Regional vCPU limit AND a per-VM-family limit.
Both must have enough headroom. For example, deploying 2x Standard_B4s_v2
nodes needs 8 vCPUs in both:
- Total Regional vCPUs (West Europe)
- Standard Bsv2 Family vCPUs (West Europe)

Check and request increases at:
https://portal.azure.com/#view/Microsoft_Azure_Capacity/QuotaMenuBlade/~/myQuotas

Filter by Provider: Microsoft.Compute, Region: your chosen region.

**VM size not available in region:**
Not all VM sizes are available in all regions. If `az aks create` fails with
"VM size not allowed", list what is available:
```bash
az vm list-skus --location <region> --resource-type virtualMachines \
  --query "[?restrictions[0].type!='Location'].{Name:name, vCPUs:capabilities[?name=='vCPUs'].value|[0], Memory:capabilities[?name=='MemoryGB'].value|[0]}" \
  -o table | head -30
```

Recommended VM sizes for SI (4 vCPUs, 16GB RAM minimum per node):
- `Standard_B4s_v2` (burstable, cheapest)
- `Standard_D4s_v3` (general purpose)
- `Standard_D4as_v5` (AMD, good value)

### Sizing

SI requires at least 2 nodes with 4 vCPUs / 16GB RAM each for a comfortable
deployment. A single 4-vCPU node will hit CPU pressure — some pods will stay
in Pending.

If constrained to 1 node for a quick POC, deploy and expect some pods to
need manual restarts once resources free up. Not recommended for production.

### Creating the cluster (step by step)

```bash
# 1. Create resource group (use a disposable name for test deployments)
az group create --name simba-intel-test --location westeurope

# 2. Create AKS cluster
az aks create \
  --resource-group simba-intel-test \
  --name simba-aks \
  --node-count 2 \
  --node-vm-size Standard_B4s_v2 \
  --generate-ssh-keys \
  --enable-managed-identity

# 3. Connect kubectl
az aks get-credentials --resource-group simba-intel-test --name simba-aks

# 4. Verify
kubectl get nodes
```

### Cleanup

Delete the entire resource group to remove all resources and stop billing:
```bash
az group delete --name simba-intel-test --yes
```

Then switch kubectl back to local:
```bash
kubectl config use-context docker-desktop   # or kind-<name>
```

### Ingress class

```yaml
ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"  # if using cert-manager
  hosts:
    - host: "simba.yourdomain.com"
      paths:
        - path: /
          pathType: ImplementationSpecific
  tls:
    - secretName: simba-intelligence-tls
      hosts:
        - simba.yourdomain.com
```

### Install

```bash
helm install si oci://docker.io/insightsoftware/simba-intelligence-chart \
  --version <VERSION> \
  -f simba-values.yaml \
  --namespace simba-intel \
  --create-namespace
```

### DNS

Get the external IP of the NGINX ingress controller:
```bash
kubectl get svc -n ingress-nginx
```

Create an A record pointing your hostname to this IP.

---

## Google GKE

### Prerequisites

- GKE cluster running Kubernetes 1.24+
- `kubectl` configured (`gcloud container clusters get-credentials <cluster>`)
- Helm 3.17+
- GKE Ingress (default) or NGINX Ingress Controller
- Outbound internet for Docker Hub or Artifact Registry mirror

### Ingress class

Using GKE default ingress:

```yaml
ingress:
  enabled: true
  className: "gce"
  annotations:
    kubernetes.io/ingress.global-static-ip-name: "simba-ip"  # pre-provisioned static IP
  hosts:
    - host: "simba.yourdomain.com"
      paths:
        - path: /
          pathType: ImplementationSpecific
```

Or with NGINX:
```yaml
ingress:
  enabled: true
  className: "nginx"
  hosts:
    - host: "simba.yourdomain.com"
      paths:
        - path: /
          pathType: ImplementationSpecific
```

### Install

```bash
helm install si oci://docker.io/insightsoftware/simba-intelligence-chart \
  --version <VERSION> \
  -f simba-values.yaml \
  --namespace simba-intel \
  --create-namespace
```

---

## Post-install (all providers)

1. Verify pods: `kubectl -n simba-intel get pods`
2. Verify ingress: `kubectl -n simba-intel get ingress`
3. Configure DNS (CNAME or A record to ingress address)
4. Access the SI UI at your configured hostname
5. Configure LLM provider — see `llm-config.md`
6. Create data connections and sources — see `post-install.md`

---

## Network requirements

Simba Intelligence requires outbound access to:

| Destination | Port | Purpose |
|---|---|---|
| LLM provider endpoints | 443 | AI capabilities |
| Customer data sources | Varies | Database queries |
| Docker Hub (install only) | 443 | Image pull |

For restricted networks, see `deployment-airgapped.md`.

---

## Oracle Cloud (OKE)

### Prerequisites

- OKE cluster running Kubernetes 1.24+
- `kubectl` configured (`oci ce cluster create-kubeconfig`)
- Helm 3.17+
- NGINX Ingress Controller or OCI Native Ingress Controller
- Outbound internet to Docker Hub or images mirrored to OCIR

### Ingress class

```yaml
ingress:
  enabled: true
  className: "nginx"
  hosts:
    - host: "simba.yourdomain.com"
      paths:
        - path: /
          pathType: ImplementationSpecific
```

### Install

```bash
helm install si oci://docker.io/insightsoftware/simba-intelligence-chart \
  --version <VERSION> \
  -f simba-values.yaml \
  --namespace simba-intel \
  --create-namespace
```

### Known issue: fully qualified image paths

OKE uses a newer Kubernetes kernel that no longer defaults to `docker.io/`
as the container image registry. Some image references in the SI and
Composer/Discovery Helm charts do not include the full registry prefix,
causing pods to fail with `ImagePullBackOff` on OKE.

This is being fixed in the 26.1 release lifecycle. Until the fix ships,
see `troubleshooting.md` § "Pods stuck in ImagePullBackOff" for the
workaround (manually patching image paths after initial deployment).

Other cloud providers (EKS, AKS, GKE) have not enforced this yet but are
expected to adopt the same behaviour in future Kubernetes versions.

---

## Known issue: fully qualified image paths (all providers)

Newer Kubernetes versions are removing the implicit `docker.io/` registry
default. Oracle Kubernetes Engine (OKE) is the first managed service to
enforce this. EKS, AKS, and GKE will follow in future K8s releases.

If pods fail with `ImagePullBackOff` and the event log shows image paths
without a `docker.io/` prefix, this is the cause. See
`troubleshooting.md` § "Pods stuck in ImagePullBackOff" for diagnosis
and workaround.

A permanent fix is expected within the 26.1 chart release lifecycle.
