# Production Ingress — DNS, TLS, and Ingress Controllers

For production deployments where SI is accessed via a proper hostname with
TLS. This replaces the port-forward + Caddy approach used in local
development.

---

## Requirements

- An ingress controller installed in the cluster (NGINX, Traefik, AWS ALB,
  GKE Ingress, HAProxy, or OpenShift Routes)
- A DNS record pointing to the ingress controller's external IP or load
  balancer
- A TLS certificate for the hostname (via cert-manager, AWS ACM, or
  manually provisioned)

---

## Values file structure

```yaml
ingress:
  appendToPath: ""
  trimTrailingSlash: true
  enabled: true
  className: "<INGRESS_CLASS>"
  annotations: {}
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

---

## Ingress class by provider

| Environment | className | Notes |
|---|---|---|
| NGINX Ingress | `nginx` | Most common on-prem and AKS |
| Traefik | `traefik` | Default on k3s, common on-prem |
| AWS ALB | `alb` | Requires AWS Load Balancer Controller |
| GKE default | `gce` | Google Cloud HTTP(S) Load Balancer |
| OpenShift | `openshift-default` | Uses Routes |

---

## TLS configuration

### Option A: cert-manager (automatic)

If cert-manager is installed with a ClusterIssuer:

```yaml
ingress:
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  tls:
    - secretName: simba-intelligence-tls
      hosts:
        - simba.yourdomain.com
```

### Option B: Pre-provisioned certificate

Create the TLS secret manually:

```bash
kubectl create namespace simba-intel
kubectl create secret tls simba-intelligence-tls \
  --cert=tls.crt \
  --key=tls.key \
  --namespace simba-intel
```

Then reference it in values:
```yaml
ingress:
  tls:
    - secretName: simba-intelligence-tls
      hosts:
        - simba.yourdomain.com
```

### Option C: AWS ACM (ALB only)

Certificate is managed by ACM, referenced by ARN in annotations:

```yaml
ingress:
  annotations:
    alb.ingress.kubernetes.io/certificate-arn: "arn:aws:acm:<region>:<account>:certificate/<id>"
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}]'
    alb.ingress.kubernetes.io/ssl-redirect: "443"
```

---

## DNS setup

After deploying, get the ingress address:

```bash
kubectl -n simba-intel get ingress
```

Create the appropriate DNS record:
- **A record**: if the ingress has a static IP
- **CNAME record**: if the ingress has a hostname (common with ALB, cloud
  load balancers)

---

## Verification

```bash
# Check ingress is provisioned
kubectl -n simba-intel get ingress

# Check TLS
curl -si https://simba.yourdomain.com/ | head -10

# Check Discovery routing
curl -si https://simba.yourdomain.com/discovery/api/user | head -10
```

Expected:
- First: HTML (SI app)
- Second: 401 JSON (Discovery is reachable)

If Discovery returns HTML, the ingress is not routing `/discovery/*`
correctly. The Helm chart should handle this automatically when ingress is
enabled — if it does not, check that `appendToPath` and `trimTrailingSlash`
are set correctly in the values file.

---

## Security headers (optional)

For production hardening, add security headers via ingress annotations:

```yaml
ingress:
  annotations:
    nginx.ingress.kubernetes.io/configuration-snippet: |
      add_header X-Content-Type-Options "nosniff" always;
      add_header X-Frame-Options "DENY" always;
      add_header X-XSS-Protection "1; mode=block" always;
      add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```
