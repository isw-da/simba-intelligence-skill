# Deploying Simba Intelligence — On-Premises Kubernetes

For deployments to customer-managed Kubernetes clusters running on-premises.
This covers any conformant Kubernetes 1.24+ distribution including Rancher
RKE/RKE2, Red Hat OpenShift, VMware Tanzu, kubeadm, and k3s.

---

## Prerequisites

- Kubernetes cluster 1.24+ with admin access
- Helm 3.17+ installed on a workstation with cluster access
- Ingress controller installed (NGINX, Traefik, HAProxy, or OpenShift Routes)
- Container registry access — either:
  - Outbound internet to Docker Hub, OR
  - Internal registry with SI images mirrored (see `deployment-airgapped.md`)
- DNS record for the SI hostname (internal or external)
- TLS certificate for the hostname (self-signed, internal CA, or public CA)

---

## Values file

```yaml
ingress:
  appendToPath: ""
  trimTrailingSlash: true
  enabled: true
  className: "<INGRESS_CLASS>"   # nginx, traefik, openshift-default, etc.
  annotations: {}
  hosts:
    - host: "simba.internal.company.com"
      paths:
        - path: /
          pathType: ImplementationSpecific
  tls:
    - secretName: simba-intelligence-tls
      hosts:
        - simba.internal.company.com
```

### TLS secret

If using a pre-existing certificate:

```bash
kubectl create secret tls simba-intelligence-tls \
  --cert=tls.crt \
  --key=tls.key \
  --namespace simba-intel
```

Create the namespace first if it does not exist:
```bash
kubectl create namespace simba-intel
```

---

## Install

```bash
helm install si oci://docker.io/insightsoftware/simba-intelligence-chart \
  --version <VERSION> \
  -f simba-values.yaml \
  --namespace simba-intel \
  --create-namespace
```

If Docker Hub is not reachable, see `deployment-airgapped.md` for
installing from a local chart archive and internal registry.

---

## OpenShift-specific notes

OpenShift uses Routes instead of Ingress by default. To use OpenShift Routes:

```yaml
ingress:
  enabled: true
  className: "openshift-default"
  annotations:
    route.openshift.io/termination: edge
  hosts:
    - host: "simba.apps.ocp.company.com"
      paths:
        - path: /
          pathType: ImplementationSpecific
```

OpenShift may also enforce Security Context Constraints (SCCs). If pods fail
to start with permission errors, the cluster admin may need to grant the
`anyuid` SCC to the SI service accounts:

```bash
oc adm policy add-scc-to-user anyuid -z default -n simba-intel
```

---

## External database (recommended for production)

For production, use an externally managed PostgreSQL instance rather than
the bundled database. This enables independent backup, scaling, and HA.

Disable bundled PostgreSQL in values:

```yaml
global:
  simba:
    intelligence:
      postgresql:
        enabled: false
```

Then provide external database connection details via the values file or
environment variables. Consult the chart's `README.md` for exact parameter
names:

```bash
helm show readme oci://docker.io/insightsoftware/simba-intelligence-chart --version <VERSION>
```

---

## Network requirements

| Destination | Port | Purpose |
|---|---|---|
| LLM provider endpoint | 443 | AI capabilities (Vertex AI, Azure OpenAI, Bedrock) |
| Customer data sources | Varies | Database connectivity |
| Docker Hub (install only) | 443 | Image pull |
| Internal DNS | 53 | Name resolution |

If the LLM provider endpoint is not reachable, SI cannot provide AI features.
For fully disconnected networks, see `deployment-airgapped.md`.

---

## Post-install

1. Verify pods: `kubectl -n simba-intel get pods`
2. Verify ingress/route: `kubectl -n simba-intel get ingress` or `oc get routes -n simba-intel`
3. Access SI at the configured hostname
4. Configure LLM provider — see `llm-config.md`
5. Create data connections — see `post-install.md`

---

## Known issue: fully qualified image paths

Newer Kubernetes versions are removing the implicit `docker.io/` registry
default. This has been observed on Oracle Kubernetes Engine (OKE) and may
affect other on-premises distributions that have upgraded to newer K8s
kernel versions.

If pods fail with `ImagePullBackOff` and the event log shows image paths
without a `docker.io/` prefix (e.g. `insightsoftware/zoomdata-web` instead
of `docker.io/insightsoftware/zoomdata-web`), this is the cause.

This affects both the SI chart and the Composer/Discovery subcharts. A
permanent fix is expected within the 26.1 chart release lifecycle.

See `troubleshooting.md` § "Pods stuck in ImagePullBackOff" for diagnosis
and the manual workaround (patching image paths after deployment).
