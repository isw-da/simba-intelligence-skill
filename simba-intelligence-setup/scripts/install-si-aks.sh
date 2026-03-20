#!/usr/bin/env bash
# =============================================================================
# Simba Intelligence Installer — Azure AKS
# =============================================================================
# Creates an AKS cluster and deploys Simba Intelligence end-to-end.
# Handles resource group, cluster creation, quota guidance, Helm install,
# and port-forward access.
#
# Usage:
#   chmod +x install-si-aks.sh
#   ./install-si-aks.sh
#
# Prerequisites:
#   - Azure CLI (az) installed and logged in
#   - Helm 3.17+ installed
#   - kubectl installed
# =============================================================================

set -euo pipefail

# --- Configuration ---
RESOURCE_GROUP="${RESOURCE_GROUP:-simba-intel-test}"
CLUSTER_NAME="${CLUSTER_NAME:-simba-aks}"
LOCATION="${LOCATION:-westeurope}"
VM_SIZE="${VM_SIZE:-Standard_B4s_v2}"
NODE_COUNT="${NODE_COUNT:-2}"
NAMESPACE="${NAMESPACE:-simba-intel}"
RELEASE_NAME="${RELEASE_NAME:-si}"
CHART_REPO="oci://docker.io/insightsoftware/simba-intelligence-chart"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }
step()  { echo -e "\n${CYAN}=== $1 ===${NC}\n"; }

# --- Step 1: Check prerequisites ---
step "Step 1: Checking prerequisites"

command -v az &>/dev/null || error "Azure CLI (az) is not installed. Install from https://learn.microsoft.com/en-us/cli/azure/install-azure-cli"
command -v helm &>/dev/null || error "Helm is not installed. Install with: brew install helm (macOS) or winget install Helm.Helm (Windows)"
command -v kubectl &>/dev/null || error "kubectl is not installed."

# Check Azure login
az account show &>/dev/null || error "Not logged in to Azure. Run: az login"
SUBSCRIPTION=$(az account show --query "name" -o tsv)
info "Azure CLI ready (subscription: $SUBSCRIPTION)"
info "Helm installed"
info "kubectl installed"

# --- Step 2: Get chart version ---
if [ -z "${CHART_VERSION:-}" ]; then
  echo ""
  read -rp "Enter SI chart version (e.g. 25.4.0): " CHART_VERSION
fi
[ -z "$CHART_VERSION" ] && error "Chart version is required."
info "Chart version: $CHART_VERSION"

# --- Step 3: Register container service provider ---
step "Step 2: Registering Azure Container Service"

REG_STATE=$(az provider show --namespace Microsoft.ContainerService --query "registrationState" -o tsv 2>/dev/null || echo "NotRegistered")
if [ "$REG_STATE" != "Registered" ]; then
  echo "Registering Microsoft.ContainerService..."
  az provider register --namespace Microsoft.ContainerService
  echo "Waiting for registration..."
  for i in {1..30}; do
    STATE=$(az provider show --namespace Microsoft.ContainerService --query "registrationState" -o tsv)
    if [ "$STATE" = "Registered" ]; then break; fi
    sleep 5
  done
  [ "$STATE" = "Registered" ] || error "Timed out waiting for provider registration."
fi
info "Microsoft.ContainerService is registered"

# --- Step 4: Create resource group ---
step "Step 3: Creating resource group"

EXISTING_RG=$(az group show --name "$RESOURCE_GROUP" 2>/dev/null || true)
if [ -n "$EXISTING_RG" ]; then
  warn "Resource group '$RESOURCE_GROUP' already exists"
  read -rp "Delete and recreate? (y/N): " RECREATE_RG
  if [[ "$RECREATE_RG" =~ ^[Yy]$ ]]; then
    echo "Deleting resource group (this may take a minute)..."
    az group delete --name "$RESOURCE_GROUP" --yes
  fi
fi
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" -o none
info "Resource group '$RESOURCE_GROUP' in $LOCATION"

# --- Step 5: Check VM quota ---
step "Step 4: Checking vCPU quota"

REQUIRED_VCPUS=$((NODE_COUNT * 4))
TOTAL_LIMIT=$(az quota show --scope "/subscriptions/$(az account show --query id -o tsv)/providers/Microsoft.Compute/locations/$LOCATION" --resource-name "cores" --query "properties.limit.value" -o tsv 2>/dev/null || echo "unknown")
TOTAL_USAGE=$(az quota show --scope "/subscriptions/$(az account show --query id -o tsv)/providers/Microsoft.Compute/locations/$LOCATION" --resource-name "cores" --query "properties.usages.value" -o tsv 2>/dev/null || echo "unknown")

if [ "$TOTAL_LIMIT" != "unknown" ] && [ "$TOTAL_USAGE" != "unknown" ]; then
  AVAILABLE=$((TOTAL_LIMIT - TOTAL_USAGE))
  if [ "$AVAILABLE" -lt "$REQUIRED_VCPUS" ]; then
    warn "Insufficient vCPU quota: need $REQUIRED_VCPUS, available $AVAILABLE (limit $TOTAL_LIMIT)"
    echo ""
    echo "Request a quota increase at:"
    echo "https://portal.azure.com/#view/Microsoft_Azure_Capacity/QuotaMenuBlade/~/myQuotas"
    echo ""
    echo "You need to increase BOTH:"
    echo "  1. Total Regional vCPUs ($LOCATION) to at least $REQUIRED_VCPUS"
    echo "  2. Standard Bsv2 Family vCPUs ($LOCATION) to at least $REQUIRED_VCPUS"
    echo ""
    echo "If quotas are greyed out, you need to upgrade from a free trial to"
    echo "Pay-As-You-Go first. Your credits carry over."
    echo ""
    read -rp "Press Enter once quota is increased, or Ctrl+C to abort: "
  else
    info "vCPU quota OK: need $REQUIRED_VCPUS, available $AVAILABLE"
  fi
else
  warn "Could not check quota automatically. If cluster creation fails with quota errors, increase your vCPU limits at https://portal.azure.com/#view/Microsoft_Azure_Capacity/QuotaMenuBlade/~/myQuotas"
fi

# --- Step 6: Create AKS cluster ---
step "Step 5: Creating AKS cluster (3-5 minutes)"

EXISTING_CLUSTER=$(az aks show --resource-group "$RESOURCE_GROUP" --name "$CLUSTER_NAME" 2>/dev/null || true)
if [ -n "$EXISTING_CLUSTER" ]; then
  warn "Cluster '$CLUSTER_NAME' already exists"
  read -rp "Delete and recreate? (y/N): " RECREATE
  if [[ "$RECREATE" =~ ^[Yy]$ ]]; then
    echo "Deleting existing cluster..."
    az aks delete --resource-group "$RESOURCE_GROUP" --name "$CLUSTER_NAME" --yes
    az aks wait --resource-group "$RESOURCE_GROUP" --name "$CLUSTER_NAME" --deleted --timeout 300 2>/dev/null || true
  else
    echo "Using existing cluster."
  fi
fi

if [ -z "$EXISTING_CLUSTER" ] || [[ "$RECREATE" =~ ^[Yy]$ ]]; then
  az aks create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$CLUSTER_NAME" \
    --node-count "$NODE_COUNT" \
    --node-vm-size "$VM_SIZE" \
    --generate-ssh-keys \
    --enable-managed-identity \
    -o none

  info "AKS cluster created"
fi

# --- Step 7: Connect kubectl ---
step "Step 6: Connecting kubectl"

az aks get-credentials --resource-group "$RESOURCE_GROUP" --name "$CLUSTER_NAME" --overwrite-existing
kubectl get nodes
info "kubectl connected to $CLUSTER_NAME"

# --- Step 8: Install SI ---
step "Step 7: Installing Simba Intelligence"

VALUES_FILE="/tmp/simba-values-aks.yaml"
cat > "$VALUES_FILE" << 'EOF'
ingress:
  enabled: false
EOF

EXISTING_RELEASE=$(helm list --namespace "$NAMESPACE" 2>/dev/null | grep "$RELEASE_NAME" || true)
if [ -n "$EXISTING_RELEASE" ]; then
  warn "Existing SI release found. Uninstalling..."
  helm uninstall "$RELEASE_NAME" --namespace "$NAMESPACE"
  kubectl delete namespace "$NAMESPACE" --ignore-not-found=true
  sleep 10
fi

helm install "$RELEASE_NAME" "$CHART_REPO" \
  --version "$CHART_VERSION" \
  -f "$VALUES_FILE" \
  --namespace "$NAMESPACE" \
  --create-namespace

info "Helm install submitted"

# --- Step 9: Wait for pods ---
step "Step 8: Waiting for pods (5-10 minutes)"

TIMEOUT=600
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
  NOT_READY=$(kubectl -n "$NAMESPACE" get pods --no-headers 2>/dev/null | grep -v "Completed" | grep -v "Running" | grep -v "Terminating" | wc -l | tr -d ' ')
  RUNNING=$(kubectl -n "$NAMESPACE" get pods --no-headers 2>/dev/null | grep "Running" | wc -l | tr -d ' ')
  TOTAL=$(kubectl -n "$NAMESPACE" get pods --no-headers 2>/dev/null | grep -v "Completed" | wc -l | tr -d ' ')

  echo -ne "\r  Pods: $RUNNING/$TOTAL running, $NOT_READY pending... (${ELAPSED}s)  "

  if [ "$NOT_READY" -eq 0 ] && [ "$RUNNING" -gt 0 ]; then
    echo ""
    info "All pods are running"
    break
  fi

  sleep 15
  ELAPSED=$((ELAPSED + 15))
done

if [ $ELAPSED -ge $TIMEOUT ]; then
  warn "Timeout. Check: kubectl -n $NAMESPACE get pods"
fi

# --- Step 10: Set up access ---
step "Step 9: Setting up local access"

CADDYFILE="/tmp/Caddyfile-aks"
cat > "$CADDYFILE" << 'EOF'
:8080 {
  @discovery path /discovery/*
  reverse_proxy @discovery host.docker.internal:8081

  reverse_proxy host.docker.internal:8082
}
EOF

pkill -f "port-forward.*simba-intelligence-chart.*8082:5050" 2>/dev/null || true
pkill -f "port-forward.*discovery-web.*8081:9050" 2>/dev/null || true
docker ps -q --filter ancestor=caddy:2 | xargs -r docker stop 2>/dev/null || true
sleep 2

kubectl -n "$NAMESPACE" port-forward "svc/${RELEASE_NAME}-simba-intelligence-chart" 8082:5050 &>/dev/null &
PF1_PID=$!
sleep 1

kubectl -n "$NAMESPACE" port-forward "svc/${RELEASE_NAME}-discovery-web" 8081:9050 &>/dev/null &
PF2_PID=$!
sleep 1

docker run --rm -d -p 8080:8080 -v "$CADDYFILE":/etc/caddy/Caddyfile caddy:2 &>/dev/null
sleep 3

# --- Done ---
echo ""
echo "============================================="
echo "  Simba Intelligence on AKS is ready!"
echo "============================================="
echo ""
echo "  URL:  http://localhost:8080"
echo "  Cluster: $CLUSTER_NAME ($LOCATION)"
echo "  Nodes: $NODE_COUNT x $VM_SIZE"
echo ""
echo "  Next steps:"
echo "    1. Log in with default admin credentials"
echo "    2. Configure LLM provider at /llm-configuration"
echo "    3. Create a data connection"
echo "    4. Create a data source with the Data Source Agent"
echo "    5. Query in the Playground"
echo ""
echo "  IMPORTANT — To stop Azure billing when done:"
echo "    az group delete --name $RESOURCE_GROUP --yes"
echo "    kubectl config use-context docker-desktop"
echo ""
echo "  To stop port-forwards:"
echo "    kill $PF1_PID $PF2_PID"
echo "    docker stop \$(docker ps -q --filter ancestor=caddy:2)"
echo ""

if command -v open &>/dev/null; then open "http://localhost:8080"; fi
