#!/usr/bin/env bash
# Engine down-driver. Tears down THIS demo's namespace only — never touches others.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

load_config

phase "teardown ${DEMO_NAME} (namespace ${NAMESPACE})"
# stop local access first
docker rm -f si-demo-caddy >/dev/null 2>&1 || true
pkill -f "port-forward.*${CHART_SVC}" 2>/dev/null || true
pkill -f "port-forward.*${DISCO_SVC}" 2>/dev/null || true
ok "stopped Caddy + port-forwards"

if [ "${1:-}" = "--keep-namespace" ]; then
  helm uninstall "$RELEASE" -n "$NAMESPACE" 2>/dev/null && ok "helm release ${RELEASE} removed" || warn "release not found"
else
  helm uninstall "$RELEASE" -n "$NAMESPACE" 2>/dev/null || true
  kubectl delete namespace "$NAMESPACE" --wait=false 2>/dev/null && ok "namespace ${NAMESPACE} deleting" || warn "namespace not found"
fi
printf '\n%s%s is down.%s\n' "$CG" "$DEMO_NAME" "$C0"
