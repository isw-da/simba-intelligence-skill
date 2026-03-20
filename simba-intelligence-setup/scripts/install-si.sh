#!/usr/bin/env bash
# =============================================================================
# Simba Intelligence Installer — macOS / Linux
# =============================================================================
# This script automates the full local deployment of Simba Intelligence.
# It checks prerequisites, creates the Helm values and Caddyfile, installs
# SI, waits for pods, sets up port-forwards + Caddy, and opens the browser.
#
# Usage:
#   chmod +x install-si.sh
#   ./install-si.sh
#
# Options:
#   CHART_VERSION  — override chart version (default: latest detected)
#   NAMESPACE      — override namespace (default: simba-intel)
#   RELEASE_NAME   — override Helm release name (default: si)
# =============================================================================

set -euo pipefail

# --- Configuration ---
NAMESPACE="${NAMESPACE:-simba-intel}"
RELEASE_NAME="${RELEASE_NAME:-si}"
CHART_REPO="oci://docker.io/insightsoftware/simba-intelligence-chart"
VALUES_FILE="/tmp/simba-values.yaml"
CADDYFILE="/tmp/Caddyfile"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# --- Step 1: Check prerequisites ---
echo ""
echo "============================================="
echo "  Simba Intelligence Installer"
echo "============================================="
echo ""
echo "Checking prerequisites..."

# Docker
if ! command -v docker &>/dev/null; then
  error "Docker is not installed. Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
fi
if ! docker info &>/dev/null; then
  error "Docker is not running. Start Docker Desktop and wait for the engine to be ready."
fi
info "Docker is running"

# kubectl
if ! command -v kubectl &>/dev/null; then
  error "kubectl is not installed. It should come with Docker Desktop, or install from https://kubernetes.io/docs/tasks/tools/"
fi

# Kubernetes cluster
if ! kubectl get nodes &>/dev/null; then
  error "No Kubernetes cluster available. Enable Kubernetes in Docker Desktop Settings, or create a kind cluster."
fi
NODE_STATUS=$(kubectl get nodes -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}')
if [ "$NODE_STATUS" != "True" ]; then
  error "Kubernetes node is not Ready. Wait for it to become Ready and try again."
fi
CONTEXT=$(kubectl config current-context)
info "Kubernetes cluster is ready (context: $CONTEXT)"

# Helm
if ! command -v helm &>/dev/null; then
  error "Helm is not installed. Install with: brew install helm (macOS) or see https://helm.sh/docs/intro/install/"
fi
info "Helm is installed"

# --- Step 2: Get chart version ---
if [ -z "${CHART_VERSION:-}" ]; then
  echo ""
  read -rp "Enter the chart version to install (e.g. 25.4.0): " CHART_VERSION
fi
if [ -z "$CHART_VERSION" ]; then
  error "Chart version is required. Find versions at https://hub.docker.com/r/insightsoftware/simba-intelligence-chart/tags"
fi
info "Using chart version: $CHART_VERSION"

# --- Step 3: Check for port collisions ---
echo ""
echo "Checking for port collisions..."
PORTS_BLOCKED=false
for PORT in 8080 8081 8082; do
  if lsof -nP -iTCP:$PORT -sTCP:LISTEN &>/dev/null; then
    warn "Port $PORT is in use:"
    lsof -nP -iTCP:$PORT -sTCP:LISTEN
    PORTS_BLOCKED=true
  fi
done
if [ "$PORTS_BLOCKED" = true ]; then
  echo ""
  read -rp "Ports are in use. Stop the processes above and press Enter to continue, or Ctrl+C to abort: "
fi
info "Ports 8080, 8081, 8082 are available"

# --- Step 4: Create values file ---
echo ""
echo "Creating values file..."
cat > "$VALUES_FILE" << 'EOF'
ingress:
  enabled: false
EOF
info "Values file written to $VALUES_FILE"

# --- Step 5: Create Caddyfile ---
cat > "$CADDYFILE" << 'EOF'
:8080 {
  @discovery path /discovery/*
  reverse_proxy @discovery host.docker.internal:8081

  reverse_proxy host.docker.internal:8082
}
EOF
info "Caddyfile written to $CADDYFILE"

# --- Step 6: Check for existing installation ---
if helm list --namespace "$NAMESPACE" 2>/dev/null | grep -q "$RELEASE_NAME"; then
  warn "Existing installation found in namespace $NAMESPACE"
  read -rp "Uninstall existing release and reinstall? (y/N): " REINSTALL
  if [[ "$REINSTALL" =~ ^[Yy]$ ]]; then
    echo "Uninstalling existing release..."
    helm uninstall "$RELEASE_NAME" --namespace "$NAMESPACE"
    kubectl delete namespace "$NAMESPACE" --ignore-not-found=true
    echo "Waiting for namespace cleanup..."
    sleep 10
    info "Previous installation removed"
  else
    error "Aborted. Remove the existing installation first."
  fi
fi

# --- Step 7: Install ---
echo ""
echo "Installing Simba Intelligence $CHART_VERSION..."
echo "This may take a few minutes on first install (downloading images)."
echo ""

helm install "$RELEASE_NAME" "$CHART_REPO" \
  --version "$CHART_VERSION" \
  -f "$VALUES_FILE" \
  --namespace "$NAMESPACE" \
  --create-namespace

info "Helm install submitted"

# --- Step 8: Wait for pods ---
echo ""
echo "Waiting for pods to become ready (timeout: 10 minutes)..."
echo "This can take 5-10 minutes on first install."
echo ""

# Wait in a loop, checking every 15 seconds
TIMEOUT=600
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
  NOT_READY=$(kubectl -n "$NAMESPACE" get pods --no-headers 2>/dev/null | grep -v "Completed" | grep -v "Running" | grep -v "Terminating" | wc -l | tr -d ' ')
  RUNNING=$(kubectl -n "$NAMESPACE" get pods --no-headers 2>/dev/null | grep "Running" | wc -l | tr -d ' ')
  TOTAL=$(kubectl -n "$NAMESPACE" get pods --no-headers 2>/dev/null | grep -v "Completed" | wc -l | tr -d ' ')

  echo -ne "\r  Pods: $RUNNING/$TOTAL running, $NOT_READY pending/initializing... (${ELAPSED}s elapsed)  "

  if [ "$NOT_READY" -eq 0 ] && [ "$RUNNING" -gt 0 ]; then
    echo ""
    info "All pods are running"
    break
  fi

  sleep 15
  ELAPSED=$((ELAPSED + 15))
done

if [ $ELAPSED -ge $TIMEOUT ]; then
  warn "Timeout waiting for pods. Some pods may still be starting."
  echo "Check status with: kubectl -n $NAMESPACE get pods"
fi

# --- Step 9: Verify services ---
echo ""
echo "Verifying services..."
SI_PORT=$(kubectl -n "$NAMESPACE" get svc "${RELEASE_NAME}-simba-intelligence-chart" -o jsonpath='{.spec.ports[0].port}' 2>/dev/null)
DISC_PORT=$(kubectl -n "$NAMESPACE" get svc "${RELEASE_NAME}-discovery-web" -o jsonpath='{.spec.ports[0].port}' 2>/dev/null)

if [ "$SI_PORT" = "5050" ] && [ "$DISC_PORT" = "9050" ]; then
  info "Services verified: main app on $SI_PORT, Discovery on $DISC_PORT"
else
  warn "Unexpected service ports. Expected 5050 and 9050, got $SI_PORT and $DISC_PORT"
fi

# --- Step 10: Start port-forwards and Caddy ---
echo ""
echo "Starting port-forwards and reverse proxy..."

# Kill any existing port-forwards
pkill -f "port-forward.*simba-intelligence-chart.*8082:5050" 2>/dev/null || true
pkill -f "port-forward.*discovery-web.*8081:9050" 2>/dev/null || true
docker ps -q --filter ancestor=caddy:2 | xargs -r docker stop 2>/dev/null || true

sleep 2

# Start port-forwards in background
kubectl -n "$NAMESPACE" port-forward "svc/${RELEASE_NAME}-simba-intelligence-chart" 8082:5050 &>/dev/null &
PF1_PID=$!
sleep 1

kubectl -n "$NAMESPACE" port-forward "svc/${RELEASE_NAME}-discovery-web" 8081:9050 &>/dev/null &
PF2_PID=$!
sleep 1

# Start Caddy in background
docker run --rm -d -p 8080:8080 -v "$CADDYFILE":/etc/caddy/Caddyfile caddy:2 &>/dev/null
CADDY_CID=$(docker ps -q --filter ancestor=caddy:2 | head -1)

sleep 3

# Verify
if curl -s http://localhost:8080/ | grep -q "html" 2>/dev/null; then
  info "Main app is accessible"
else
  warn "Main app not responding yet — may need a few more seconds"
fi

if curl -s http://localhost:8080/discovery/api/user 2>/dev/null | grep -q "401\|Unauthorized" 2>/dev/null; then
  info "Discovery is accessible"
else
  warn "Discovery not responding yet — may need a few more seconds"
fi

# --- Done ---
echo ""
echo "============================================="
echo "  Simba Intelligence is ready!"
echo "============================================="
echo ""
echo "  URL:  http://localhost:8080"
echo ""
echo "  Next steps:"
echo "    1. Log in with the default admin credentials"
echo "    2. Configure your LLM provider at /llm-configuration"
echo "    3. Create a data connection"
echo "    4. Create a data source with the Data Source Agent"
echo "    5. Query your data in the Playground"
echo ""
echo "  To stop:"
echo "    kill $PF1_PID $PF2_PID        # stop port-forwards"
echo "    docker stop $CADDY_CID    # stop Caddy"
echo ""
echo "  To uninstall:"
echo "    helm uninstall $RELEASE_NAME -n $NAMESPACE"
echo "    kubectl delete namespace $NAMESPACE"
echo ""

# Open browser
if command -v open &>/dev/null; then
  open "http://localhost:8080"
elif command -v xdg-open &>/dev/null; then
  xdg-open "http://localhost:8080"
fi
