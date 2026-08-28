#!/usr/bin/env bash
# =============================================================================
# Simba Intelligence — Double-Click Installer for macOS
# =============================================================================
# Save this file as "Install Simba Intelligence.command"
# Then: right-click → Open (first time only, to bypass Gatekeeper)
#
# After that, double-click to run anytime.
# =============================================================================

set -euo pipefail
cd "$(dirname "$0")"

clear
echo "============================================="
echo "  Simba Intelligence Installer"
echo "  macOS — Local Development"
echo "============================================="
echo ""

# --- Colors ---
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}!${NC} $1"; }
fail()  { echo -e "${RED}✗ $1${NC}"; echo ""; echo "Press Enter to close."; read; exit 1; }

# --- Check Docker ---
echo "Checking prerequisites..."
command -v docker &>/dev/null || fail "Docker is not installed. Download from https://www.docker.com/products/docker-desktop/"
docker info &>/dev/null || fail "Docker Desktop is not running. Open it and wait for 'Engine running'."
info "Docker is running"

# --- Check Kubernetes ---
if ! kubectl get nodes &>/dev/null; then
  fail "Kubernetes is not running. In Docker Desktop: Settings → Kubernetes → Enable Kubernetes"
fi
info "Kubernetes is ready"

# --- Check Helm ---
if ! command -v helm &>/dev/null; then
  echo ""
  echo "Helm is not installed. Installing via Homebrew..."
  if command -v brew &>/dev/null; then
    brew install helm
  else
    fail "Homebrew is not installed. Install from https://brew.sh then re-run this installer."
  fi
fi
info "Helm is installed"

# --- Chart version ---
echo ""
echo "Find versions at: https://hub.docker.com/r/insightsoftware/simba-intelligence-chart/tags"
echo ""
read -rp "Chart version to install (e.g. 26.2.1): " CHART_VERSION
[ -z "$CHART_VERSION" ] && fail "Version is required."

# --- Port check ---
echo ""
echo "Checking ports..."
BLOCKED=false
for PORT in 8080 8081 8082; do
  if lsof -nP -iTCP:$PORT -sTCP:LISTEN &>/dev/null; then
    warn "Port $PORT is in use"
    BLOCKED=true
  fi
done
if [ "$BLOCKED" = true ]; then
  echo ""
  echo "Some ports are occupied."
  # Only ever stop what a previous run of THIS script started. The old code
  # ran `docker ps --filter ancestor=caddy:2 | xargs docker stop` and
  # `pkill -f port-forward...`, which stop any caddy:2 container and any
  # process merely mentioning the string on the whole machine.
  if [ -f /tmp/simba-si-caddy.cid ]; then
    docker stop "$(cat /tmp/simba-si-caddy.cid)" &>/dev/null || true
    rm -f /tmp/simba-si-caddy.cid
  fi
  if [ -f /tmp/simba-si-portforward.pids ]; then
    while read -r P; do
      [ -n "$P" ] && ps -p "$P" -o command= 2>/dev/null | grep -q port-forward && kill "$P" 2>/dev/null || true
    done < /tmp/simba-si-portforward.pids
    rm -f /tmp/simba-si-portforward.pids
  fi
  sleep 2
  STILL=""
  for PORT in 8080 8081 8082; do
    lsof -nP -iTCP:$PORT -sTCP:LISTEN &>/dev/null && STILL="$STILL $PORT"
  done
  if [ -n "$STILL" ]; then
    warn "Ports still in use:$STILL"
    warn "Something else on this machine is holding them. Stop it, then run this again."
    echo "Press Enter to close."; read; exit 1
  fi
fi
info "Ports ready"

# --- Check existing install ---
if helm list --namespace simba-intel 2>/dev/null | grep -q "si"; then
  echo ""
  warn "SI is already installed."
  read -rp "Uninstall and reinstall? (y/N): " REINSTALL
  if [[ "$REINSTALL" =~ ^[Yy]$ ]]; then
    echo "Removing..."
    helm uninstall si --namespace simba-intel 2>/dev/null || true
    kubectl delete namespace simba-intel --ignore-not-found=true 2>/dev/null || true
    sleep 10
    info "Previous install removed"
  else
    echo "Skipping install. Setting up access only..."
  fi
fi

# --- Install ---
if ! helm list --namespace simba-intel 2>/dev/null | grep -q "si"; then
  echo ""
  echo "Installing Simba Intelligence $CHART_VERSION..."
  echo "(This takes 5-10 minutes on first install)"
  echo ""

  cat > /tmp/simba-values.yaml << 'EOF'
ingress:
  enabled: false
EOF

  helm install si oci://docker.io/insightsoftware/simba-intelligence-chart \
    --version "$CHART_VERSION" \
    -f /tmp/simba-values.yaml \
    --namespace simba-intel \
    --create-namespace

  info "Helm install submitted"

  echo ""
  echo "Waiting for pods..."
  TIMEOUT=600; ELAPSED=0
  while [ $ELAPSED -lt $TIMEOUT ]; do
    NOT_READY=$(kubectl -n simba-intel get pods --no-headers 2>/dev/null | grep -v "Completed" | grep -v "Running" | grep -v "Terminating" | wc -l | tr -d ' ')
    RUNNING=$(kubectl -n simba-intel get pods --no-headers 2>/dev/null | grep "Running" | wc -l | tr -d ' ')
    TOTAL=$(kubectl -n simba-intel get pods --no-headers 2>/dev/null | grep -v "Completed" | wc -l | tr -d ' ')
    echo -ne "\r  $RUNNING/$TOTAL running, $NOT_READY pending... (${ELAPSED}s)  "
    if [ "$NOT_READY" -eq 0 ] && [ "$RUNNING" -gt 0 ]; then echo ""; info "All pods running"; break; fi
    sleep 15; ELAPSED=$((ELAPSED + 15))
  done
fi

# --- Access ---
echo ""
echo "Setting up access..."

cat > /tmp/Caddyfile << 'EOF'
:8080 {
  @discovery path /discovery/*
  reverse_proxy @discovery host.docker.internal:8081
  reverse_proxy host.docker.internal:8082
}
EOF

sleep 1

kubectl -n simba-intel port-forward svc/si-simba-intelligence-chart 8082:5050 &>/dev/null &
PF1=$!
kubectl -n simba-intel port-forward svc/si-discovery-web 8081:9050 &>/dev/null &
PF2=$!
printf '%s\n%s\n' "$PF1" "$PF2" > /tmp/simba-si-portforward.pids
sleep 2
# Keep the id docker gives us rather than re-querying by image.
CADDY_CID=$(docker run --rm -d -p 8080:8080 -v /tmp/Caddyfile:/etc/caddy/Caddyfile caddy:2 2>/dev/null)
echo "$CADDY_CID" > /tmp/simba-si-caddy.cid
sleep 3

# --- Done ---
echo ""
echo "============================================="
echo "  Simba Intelligence is ready!"
echo "============================================="
echo ""
echo "  Opening http://localhost:8080 ..."
echo ""
echo "  Username: admin"
echo "  Password: read it from the cluster, it is generated per install:"
echo "    kubectl -n simba-intel get secret si-discovery-web \\"
echo "      -o jsonpath='{.data.admin\\.password}' | base64 -d"
echo ""
echo "  (This used to print a hardcoded default here. The password is a"
echo "   per-install secret, so read it rather than assume it.)"
echo ""
echo "  Next: Configure your LLM at /llm-configuration"
echo ""
echo "  To stop: close this window"
echo "  To uninstall: helm uninstall si -n simba-intel"
echo ""

open "http://localhost:8080"

echo "Press Enter to stop SI and close."
read
# Stop only this run's processes. `pkill -f "port-forward.*simba-intel"`
# matched any command line containing that text anywhere on the machine.
kill "$PF1" "$PF2" 2>/dev/null || true
[ -n "$CADDY_CID" ] && docker stop "$CADDY_CID" &>/dev/null || true
rm -f /tmp/simba-si-portforward.pids /tmp/simba-si-caddy.cid
echo "Stopped."
