# Deploying Simba Intelligence — Air-Gapped / Disconnected

For environments with no outbound internet access. This covers mirroring
container images to an internal registry and installing from a local Helm
chart archive.

---

## Overview

An air-gapped install requires three things prepared on a connected machine
and transferred to the disconnected environment:

1. **Helm chart archive** (.tgz file)
2. **Container images** (transferred to internal registry)
3. **Values file** configured to pull from the internal registry

---

## Step 1: Prepare on a connected machine

### Download the Helm chart

```bash
helm pull oci://docker.io/insightsoftware/simba-intelligence-chart \
  --version <VERSION>
```

This creates `simba-intelligence-chart-<VERSION>.tgz`.

### Identify required images

Extract the chart and inspect:

```bash
tar -xzf simba-intelligence-chart-<VERSION>.tgz
cd simba-intelligence-chart/

# List images referenced in the chart
grep -r "image:" templates/ | sort -u
grep -r "repository:" values.yaml
```

Also check subchart images:
```bash
ls charts/
# For each subchart, inspect its values.yaml for image references
```

### Pull and save images

Pull each required image and save to a tar archive:

```bash
# Example — repeat for each image identified above
docker pull insightsoftware/simba-intelligence-chart:<VERSION>
docker pull insightsoftware/zoomdata-web:<VERSION>
docker pull insightsoftware/zoomdata-query-engine:<VERSION>
# ... all other images

# Save all to a single archive
docker save -o simba-images.tar \
  insightsoftware/simba-intelligence-chart:<VERSION> \
  insightsoftware/zoomdata-web:<VERSION> \
  insightsoftware/zoomdata-query-engine:<VERSION>
  # ... all other images
```

### Transfer to disconnected environment

Transfer these files to the air-gapped environment:
- `simba-intelligence-chart-<VERSION>.tgz`
- `simba-images.tar`
- `simba-values.yaml` (prepared for internal registry)

Use USB drive, approved file transfer mechanism, or data diode per your
organisation's security policy.

---

## Step 2: Load images into internal registry

On a machine inside the air-gapped network with access to the internal
container registry:

```bash
# Load images into local Docker
docker load -i simba-images.tar

# Tag and push to internal registry
docker tag insightsoftware/simba-intelligence-chart:<VERSION> \
  registry.internal.company.com/simba/simba-intelligence-chart:<VERSION>

docker push registry.internal.company.com/simba/simba-intelligence-chart:<VERSION>

# Repeat for all images
```

If using a registry that supports bulk import (Harbor, Artifactory), consult
its documentation for more efficient methods.

---

## Step 3: Configure values for internal registry

Create a values file that overrides all image repositories to point to the
internal registry:

```yaml
ingress:
  enabled: true
  className: "nginx"
  hosts:
    - host: "simba.internal.company.com"
      paths:
        - path: /
          pathType: ImplementationSpecific
  tls:
    - secretName: simba-intelligence-tls
      hosts:
        - simba.internal.company.com

# Override image registry globally if supported by the chart
# Check values.yaml for exact parameter names:
#   global.imageRegistry or per-component image.repository
```

Consult the chart's values.yaml for the exact parameters to override image
repositories:

```bash
# On the connected machine before transfer:
helm show values oci://docker.io/insightsoftware/simba-intelligence-chart \
  --version <VERSION> | grep -A2 "repository\|registry\|image"
```

---

## Step 4: Install from local chart

```bash
helm install si ./simba-intelligence-chart-<VERSION>.tgz \
  -f simba-values.yaml \
  --namespace simba-intel \
  --create-namespace
```

---

## Step 5: Verify

```bash
kubectl -n simba-intel get pods
kubectl -n simba-intel get ingress
```

If pods are stuck in `ImagePullBackOff`, the internal registry is not
reachable from the cluster or the image tag does not match. Check:

```bash
kubectl -n simba-intel describe pod <pod-name>
# Look at the Events section for the exact image it is trying to pull
```

---

## LLM provider in air-gapped environments

SI requires an LLM provider for AI capabilities. In an air-gapped
environment, the LLM provider must be reachable from the cluster's network.

Options:
- **Ollama + LiteLLM** (recommended for local/POC) — runs entirely on the
  local machine with no network access needed. See `references/llm-config.md`
  § "Air-gapped / local LLM" for full setup instructions.
- **Self-hosted LLM** behind an OpenAI-compatible API endpoint — configure
  via the LiteLLM proxy approach described in `references/llm-config.md`
- **Network exception** for outbound 443 to a specific LLM provider endpoint
  (e.g. Vertex AI, Azure OpenAI) via proxy or firewall rule
- **AWS Bedrock via VPC endpoint** — no public internet needed if Bedrock
  is in the same AWS region with a VPC endpoint configured

If no LLM is reachable at all, SI will deploy and run but AI features
(Data Source Agent, Playground natural language querying) will not function.
Data connections and manual data source configuration will still work.

---

## Upgrades in air-gapped environments

Repeat the process: pull new chart + images on connected machine, transfer,
load into registry, then:

```bash
helm upgrade si ./simba-intelligence-chart-<NEW_VERSION>.tgz \
  -f simba-values.yaml \
  --namespace simba-intel
```
