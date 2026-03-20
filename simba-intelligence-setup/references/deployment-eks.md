# Deploying Simba Intelligence — AWS EKS

End-to-end guide for deploying SI on Amazon Elastic Kubernetes Service.
Based on real production deployments.

---

## Prerequisites

### Required tools

| Tool | Install (Windows) | Install (macOS) | Verify |
|---|---|---|---|
| AWS CLI | `msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi` | `brew install awscli` | `aws --version` |
| eksctl | `choco install eksctl -y` | `brew install eksctl` | `eksctl version` |
| kubectl | `choco install kubernetes-cli -y` | `brew install kubectl` | `kubectl version --client` |
| Helm | `choco install kubernetes-helm` | `brew install helm` | `helm version` |

### Configure AWS CLI

```bash
aws configure
# Enter: Access Key ID, Secret Access Key, region (e.g. us-east-2), output format (json)
```

Verify credentials:
```bash
aws sts get-caller-identity
```

### Required IAM policies

The IAM user or role running these commands needs:

- **AmazonEKSClusterPolicy** — allows creating and managing EKS clusters
- **AmazonEC2FullAccess** — allows creating EC2 instances for worker nodes
- **AWSCloudFormationFullAccess** — eksctl uses CloudFormation under the hood

Verify they exist:
```bash
aws iam list-policies --query 'Policies[?PolicyName==`AmazonEKSClusterPolicy`]'
aws iam list-policies --query 'Policies[?PolicyName==`AmazonEC2FullAccess`]'
aws iam list-policies --query 'Policies[?PolicyName==`AWSCloudFormationFullAccess`]'
```

If any are missing, attach them to the IAM user or role in the AWS Console
under IAM → Users → Permissions → Add permissions.

---

## Step 1: Create the EKS cluster

Check available zones in the chosen region:
```bash
aws ec2 describe-availability-zones --region us-east-2
```

Create the cluster:
```bash
eksctl create cluster \
  --name simba-intel \
  --version 1.34 \
  --region us-east-2 \
  --zones us-east-2a,us-east-2b \
  --nodegroup-name simba-intel-nodegroup \
  --node-volume-size 20 \
  --node-type m5a.2xlarge \
  --nodes 1
```

What each flag does:
- `--name` — cluster name shown in the EKS dashboard
- `--version` — Kubernetes version (use the latest stable from AWS docs)
- `--region` — AWS region for the worker nodes
- `--zones` — availability zones (need at least two for HA)
- `--nodegroup-name` — name for the node group (for scaling later)
- `--node-volume-size` — storage per node in GB
- `--node-type` — EC2 instance type. `m5a.2xlarge` gives 8 vCPUs and 32GB RAM
- `--nodes` — number of worker nodes (1 is enough for a POC)

This takes 10-15 minutes. eksctl creates a CloudFormation stack behind the scenes.

Verify:
```bash
kubectl get nodes -o wide
```

---

## Step 2: Set up EBS storage provisioning

SI uses persistent volumes for databases. EKS needs the EBS CSI driver to
provision them.

### Create IAM OIDC identity provider

```bash
eksctl utils associate-iam-oidc-provider \
  --region us-east-2 \
  --cluster simba-intel \
  --approve
```

### Verify OIDC

```bash
aws eks describe-cluster --name simba-intel \
  --query "cluster.identity.oidc.issuer"
```

### Check EBS CSI driver policy exists

```bash
aws iam list-policies --query 'Policies[?PolicyName==`AmazonEBSCSIDriverPolicy`]'
```

### Create IAM service account and install EBS CSI addon

```bash
eksctl create iamserviceaccount \
  --name ebs-csi-controller-sa \
  --namespace kube-system \
  --cluster simba-intel \
  --attach-policy-arn arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy \
  --approve \
  --override-existing-serviceaccounts \
  --role-name AmazonEKS_EBS_CSI_DriverRole \
  --role-only \
  --region us-east-2
```

Then install the addon (replace the account ID with the user's AWS account):
```bash
eksctl create addon \
  --name aws-ebs-csi-driver \
  --cluster simba-intel \
  --service-account-role-arn arn:aws:iam::<ACCOUNT_ID>:role/AmazonEKS_EBS_CSI_DriverRole \
  --region us-east-2 \
  --force
```

### Create the StorageClass

Save as `deployment.yaml`:
```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ebs-sc
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: ebs.csi.aws.com
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
```

Apply:
```bash
kubectl apply -f deployment.yaml
```

Verify `ebs-sc` is the default:
```bash
kubectl get storageclass
```

It should show `ebs-sc (default)`.

---

## Step 3: Create namespace

```bash
kubectl create namespace simba-intel
```

---

## Step 4: (Optional) Add EDC connector drivers

If the deployment needs custom JDBC drivers (e.g. Workday), use a shared
persistent volume to upload them.

Create PV and PVC:
```yaml
# driver-volume.yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: composer-shared-volume
spec:
  capacity:
    storage: 1Gi
  volumeMode: Filesystem
  accessModes:
    - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  storageClassName: "ebs-sc"
  hostPath:
    path: "/mnt"
```

```yaml
# driver-upload.yaml
apiVersion: v1
kind: Pod
metadata:
  name: "drivers-setup"
spec:
  volumes:
  - name: drivers-setup
    persistentVolumeClaim:
      claimName: composer-shared-volume
  containers:
  - name: drivers-setup
    image: busybox
    command: ["/bin/sh", "-c", "sleep infinity"]
    volumeMounts:
    - name: drivers-setup
      mountPath: /mnt
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: composer-shared-volume
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 1Gi
  storageClassName: "ebs-sc"
```

Apply and upload drivers:
```bash
kubectl apply -f driver-volume.yaml -n simba-intel
kubectl apply -f driver-upload.yaml -n simba-intel

# Create target directory and copy drivers
kubectl exec -it drivers-setup -- mkdir -p /mnt/edc-workday/drivers
kubectl cp path/to/driver/libs/. drivers-setup:/mnt/edc-workday/drivers/

# Release the PV for SI to use
kubectl patch pv composer-shared-volume -p '{"spec":{"claimRef": null}}'
```

---

## Step 5: Install Simba Intelligence

### Values file

Save as `base.yaml`:
```yaml
discovery:
  zoomdataWeb:
    adminPassword: "SimbaIntelligence123456!"
    properties:
      http.response.header.content-security-policy.frame-ancestors: '*'
      access.control.allow.origin: '*'
      logging.dir: /opt/zoomdata/logs
    extraEnvs:
      - name: LOG_CONSOLE_LEVEL
        value: INFO
      - name: LOG_FILE_LEVEL
        value: INFO

ingress:
  appendToPath: ""
  trimTrailingSlash: true
  enabled: true
  className: "traefik"
  annotations: {}
  hosts:
    - paths:
      - path: /
        pathType: ImplementationSpecific
```

Notes on this values file:
- `adminPassword` — sets the admin login password (change for production)
- `frame-ancestors: '*'` — allows SI to be embedded in iframes (needed for
  some integrations; restrict in production)
- `access.control.allow.origin: '*'` — CORS permissive (restrict in production)
- `ingress.enabled: true` with Traefik — uses Traefik as the ingress controller

### Install

```bash
helm install si oci://docker.io/insightsoftware/simba-intelligence-chart \
  --version <VERSION> \
  --namespace simba-intel \
  -f base.yaml
```

### Wait for pods

```bash
kubectl get pods -n simba-intel -w
```

---

## Step 6: Set up Traefik ingress for public access

Install Traefik as a LoadBalancer to get a public URL:

```bash
helm repo add traefik https://helm.traefik.io/traefik
helm repo update

helm upgrade --install traefik traefik/traefik \
  --namespace kube-system \
  --set service.type=LoadBalancer \
  --set ports.web.enabled=true \
  --set ports.web.port=80 \
  --set ports.websecure.enabled=true \
  --set ports.websecure.port=443
```

### Create ingress rules for SI routing

Save as `rewriteIngress.yaml`:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: si-simba-intelligence-chart-ingress
  namespace: default
  annotations:
    kubernetes.io/ingress.class: traefik
spec:
  ingressClassName: traefik
  rules:
  - http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: si-simba-intelligence-chart
            port:
              number: 5050
      - path: /mcp
        pathType: Prefix
        backend:
          service:
            name: si-simba-intelligence-chart-mcp
            port:
              number: 8000
      - path: /discovery
        pathType: Prefix
        backend:
          service:
            name: si-discovery-web
            port:
              number: 9050
```

Apply:
```bash
kubectl apply -f rewriteIngress.yaml
```

Note the three routing rules:
- `/` → main SI app (port 5050)
- `/mcp` → MCP server (port 8000)
- `/discovery` → Discovery web (port 9050)

### Get the public URL

```bash
kubectl get svc traefik -n kube-system
```

The EXTERNAL-IP is the load balancer address. Access SI at that IP or create
a DNS record pointing to it.

---

## Step 7: Post-install

1. Log in with default credentials: `admin` / `SimbaIntelligence123456!`
2. Configure LLM provider at `/llm-configuration` — see `llm-config.md`
3. Create data connections — see `post-install.md`

---

## Teardown

```bash
helm uninstall si --namespace simba-intel
kubectl delete namespace simba-intel
eksctl delete cluster --region us-east-2 --name simba-intel
```

The `eksctl delete cluster` command removes the CloudFormation stack,
worker nodes, and all associated resources. This stops all AWS billing
for the cluster.

---

## Key differences from AKS

| Aspect | EKS | AKS |
|---|---|---|
| Cluster creation | `eksctl` (CloudFormation) | `az aks create` |
| Storage | EBS CSI driver must be installed separately | Managed disks work out of the box |
| Ingress | Traefik or ALB Controller (install separately) | NGINX or built-in |
| IAM | Multiple policies + OIDC provider + service accounts | Managed identity (simpler) |
| Time to create cluster | 10-15 minutes | 3-5 minutes |
| Teardown | `eksctl delete cluster` | `az group delete` |

EKS requires more upfront setup (storage driver, IAM, OIDC) than AKS.
Budget extra time for EKS deployments.
