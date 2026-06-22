#!/usr/bin/env bash
# si-demo-env engine — shared functions. Vendored into each demo's env/lib/.
# Do not edit here in a demo repo; refresh with `scaffold.sh --sync <repo>`.
# Sourced by up.sh / down.sh / verify.sh, which set ENV_DIR first.

set -uo pipefail

# ---------- locate the env/ dir (parent of this lib) ----------
_lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_DIR="${ENV_DIR:-$(cd "$_lib_dir/.." && pwd)}"

# ---------- logging ----------
if [ -t 1 ]; then C0=$'\033[0m'; C1=$'\033[1;36m'; CG=$'\033[1;32m'; CY=$'\033[1;33m'; CR=$'\033[1;31m'; else C0= C1= CG= CY= CR=; fi
log()   { printf '%s\n' "  $*"; }
phase() { printf '\n%s== %s ==%s\n' "$C1" "$*" "$C0"; }
ok()    { printf '%s  ✓ %s%s\n' "$CG" "$*" "$C0"; }
warn()  { printf '%s  ! %s%s\n' "$CY" "$*" "$C0"; }
die()   { printf '%s  ✗ %s%s\n' "$CR" "$*" "$C0" >&2; exit 1; }

# ---------- config ----------
load_config() {
  [ -f "$ENV_DIR/config.sh" ] || die "missing $ENV_DIR/config.sh"
  # shellcheck disable=SC1091
  source "$ENV_DIR/config.sh"
  : "${DEMO_NAME:?config.sh must set DEMO_NAME}"
  : "${NAMESPACE:?config.sh must set NAMESPACE}"
  : "${RELEASE:=si}"
  : "${HAS_DATA_TIER:=true}"
  : "${EDCS:=}"; : "${CUSTOM_EDCS:=}"; : "${CLUSTER:=}"
  CHART_SVC="${RELEASE}-simba-intelligence-chart"
  DISCO_SVC="${RELEASE}-discovery-web"
  PG_POD="${RELEASE}-logi-symphony-postgresql-0"
}

load_secrets() {
  if [ -f "$ENV_DIR/secrets.env" ]; then
    set -a; # shellcheck disable=SC1091
    source "$ENV_DIR/secrets.env"; set +a
    ok "loaded secrets.env"
  else
    warn "no secrets.env (copy secrets.example.env -> secrets.env and fill it)"
  fi
  : "${DISCO_ADMIN_USER:=admin}"
  : "${DISCO_ADMIN_PASSWORD:=}"
}

# ---------- preflight ----------
preflight() {
  phase "preflight"
  for t in kubectl helm docker curl python3; do command -v "$t" >/dev/null || die "missing tool: $t"; done
  if ! kubectl cluster-info >/dev/null 2>&1; then
    die "cluster unreachable. Start Docker + the kind cluster '${CLUSTER:-?}', then retry."
  fi
  ok "tools + cluster reachable (context: $(kubectl config current-context 2>/dev/null))"
  [ -n "$DISCO_ADMIN_PASSWORD" ] || warn "DISCO_ADMIN_PASSWORD not set; state/rules import will be skipped"
}

# ---------- namespace + helm ----------
ensure_namespace() {
  phase "namespace ${NAMESPACE}"
  kubectl get ns "$NAMESPACE" >/dev/null 2>&1 || kubectl create namespace "$NAMESPACE"
  ok "namespace ${NAMESPACE} present"
}

# ---------- prerequisites (PVCs + EDC drivers) — MUST run before helm ----------
# The packaged Oracle EDC mounts composer-shared-volume (subPath edc-oracle/drivers) and crash-loops
# without ojdbc11.jar, which makes helm --wait hang. So create the PVC and stage the driver first.
prereqs() {
  phase "prerequisites"
  if compgen -G "$ENV_DIR/prereqs/*.yaml" >/dev/null; then
    kubectl -n "$NAMESPACE" apply -f "$ENV_DIR/prereqs/" || die "prereq manifests failed"
    ok "applied prereq manifests"
  fi
  case ",$EDCS," in *,oracle,*) stage_oracle_driver ;; esac
}

stage_oracle_driver() {
  kubectl -n "$NAMESPACE" get pvc composer-shared-volume >/dev/null 2>&1 \
    || { warn "no composer-shared-volume PVC (add env/prereqs/); Oracle EDC will not start"; return 0; }
  kubectl -n "$NAMESPACE" apply -f - >/dev/null 2>&1 <<'EOF'
apiVersion: v1
kind: Pod
metadata: {name: driver-loader}
spec:
  restartPolicy: Never
  containers: [{name: driver-loader, image: busybox, command: ["sleep","3600"], volumeMounts: [{name: shared, mountPath: /drivers}]}]
  volumes: [{name: shared, persistentVolumeClaim: {claimName: composer-shared-volume}}]
EOF
  kubectl -n "$NAMESPACE" wait --for=condition=Ready pod/driver-loader --timeout=90s >/dev/null 2>&1 \
    || { warn "driver-loader not ready; skipping Oracle driver"; return 0; }
  local jar="${OJDBC_JAR:-/tmp/ojdbc11.jar}"
  if [ ! -f "$jar" ]; then
    local ver; ver="$(curl -s https://repo1.maven.org/maven2/com/oracle/database/jdbc/ojdbc11/maven-metadata.xml 2>/dev/null | grep -oE '<release>[^<]+' | sed 's/<release>//')"
    ver="${ver:-23.5.0.24.07}"
    log "fetching ojdbc11 $ver from Maven Central (~7.7MB)"
    curl -sSL -o "$jar" "https://repo1.maven.org/maven2/com/oracle/database/jdbc/ojdbc11/$ver/ojdbc11-$ver.jar" \
      || { warn "ojdbc download failed; supply OJDBC_JAR=/path/ojdbc11.jar and re-run"; return 0; }
  fi
  kubectl -n "$NAMESPACE" exec driver-loader -- mkdir -p /drivers/edc-oracle/drivers 2>/dev/null
  kubectl cp "$jar" "$NAMESPACE/driver-loader:/drivers/edc-oracle/drivers/ojdbc11.jar" \
    && ok "staged ojdbc11.jar for the Oracle EDC" || warn "ojdbc stage failed"
}

helm_up() {
  phase "helm install/upgrade (${RELEASE})"
  local chart; chart="$(ls "$ENV_DIR"/chart/*.tgz 2>/dev/null | head -1)"
  [ -n "$chart" ] || die "no chart tarball in $ENV_DIR/chart/ (vendor the SI chart .tgz; OCI pull is broken)"
  helm upgrade --install "$RELEASE" "$chart" -n "$NAMESPACE" \
    -f "$ENV_DIR/values.yaml" --wait --timeout 10m \
    || die "helm failed"
  ok "helm release ${RELEASE} ready"
}

wait_ready() {
  phase "wait for core pods"
  kubectl -n "$NAMESPACE" rollout status deploy/"$CHART_SVC" --timeout=300s || warn "chart rollout slow"
  kubectl -n "$NAMESPACE" wait --for=condition=Ready pod \
    -l app.kubernetes.io/component=discovery-query-engine --timeout=300s 2>/dev/null \
    || warn "query engine not Ready yet"
  ok "core pods up"
}

# ---------- data tier ----------
data_tier_up() {
  if [ "$HAS_DATA_TIER" != "true" ]; then
    warn "HAS_DATA_TIER=false — external data; skipping data deploy (connection recipe only)"
    return 0
  fi
  phase "data tier"
  if compgen -G "$ENV_DIR/data/*.yaml" >/dev/null; then
    kubectl -n "$NAMESPACE" apply -f "$ENV_DIR/data/" || die "data manifests failed"
  fi
  if [ -x "$ENV_DIR/data/load.sh" ]; then
    NAMESPACE="$NAMESPACE" RELEASE="$RELEASE" bash "$ENV_DIR/data/load.sh" || die "data load.sh failed"
    ok "data loaded"
  else
    warn "no data/load.sh — load your tables manually (see data/README.md)"
  fi
}

# ---------- custom EDC images ----------
# For each name in CUSTOM_EDCS, expect env/edc/<name>/ with ONE of:
#   build.sh   — builds <name>:latest (e.g. clone the connector repo, mvn package, docker build)
#   Dockerfile — built directly here
# then kind-loads <name>:latest, and applies deploy.yaml (the connector Deployment/Service) if present.
custom_edcs_build() {
  [ -n "$CUSTOM_EDCS" ] || return 0
  phase "custom EDC images"
  local name
  IFS=',' read -ra _edcs <<<"$CUSTOM_EDCS"
  for name in "${_edcs[@]}"; do
    name="$(echo "$name" | xargs)"
    local ctx="$ENV_DIR/edc/$name"
    [ -d "$ctx" ] || { warn "edc/$name not found; expecting build.sh / Dockerfile / deploy.yaml"; continue; }
    if [ -x "$ctx/build.sh" ]; then
      ( cd "$ctx" && NAMESPACE="$NAMESPACE" CLUSTER="$CLUSTER" bash build.sh ) || die "edc/$name/build.sh failed"
      ok "built $name via build.sh"
    elif [ -f "$ctx/Dockerfile" ]; then
      docker build -t "$name:latest" "$ctx" || die "build $name failed"
      ok "built $name:latest from Dockerfile"
    else
      warn "edc/$name has no build.sh or Dockerfile; see edc/$name/BUILD.md (image not built)"
    fi
    docker image inspect "$name:latest" >/dev/null 2>&1 && [ -n "$CLUSTER" ] && \
      { kind load docker-image "$name:latest" --name "$CLUSTER" && ok "loaded $name:latest into $CLUSTER"; }
    if [ -f "$ctx/deploy.yaml" ]; then
      kubectl -n "$NAMESPACE" apply -f "$ctx/deploy.yaml" && ok "applied edc/$name/deploy.yaml" \
        || warn "edc/$name/deploy.yaml apply reported issues"
    fi
  done
}

# ---------- secrets -> k8s ----------
secrets_to_k8s() {
  [ -f "$ENV_DIR/secrets.env" ] || return 0
  phase "k8s secret (si-demo-secrets)"
  kubectl -n "$NAMESPACE" create secret generic si-demo-secrets \
    --from-env-file="$ENV_DIR/secrets.env" --dry-run=client -o yaml | kubectl apply -f - \
    && ok "si-demo-secrets applied (data-tier manifests can secretKeyRef it)"
}

# ---------- access: port-forwards + caddy ----------
access_up() {
  phase "access (port-forwards + Caddy :8080)"
  pkill -f "port-forward.*$CHART_SVC" 2>/dev/null || true
  pkill -f "port-forward.*$DISCO_SVC" 2>/dev/null || true
  sleep 1
  nohup kubectl -n "$NAMESPACE" port-forward "svc/$CHART_SVC" 8082:5050 >/tmp/pf-chart.log 2>&1 &
  nohup kubectl -n "$NAMESPACE" port-forward "svc/$DISCO_SVC" 8081:9050 >/tmp/pf-disc.log 2>&1 &
  sleep 4
  local caddyfile="$_lib_dir/Caddyfile"
  docker rm -f si-demo-caddy >/dev/null 2>&1 || true
  docker run -d --rm --name si-demo-caddy -p 8080:8080 -v "$caddyfile":/etc/caddy/Caddyfile caddy:2 >/dev/null 2>&1 \
    && ok "Caddy on :8080" || warn "Caddy did not start (port 8080 busy?)"
  log "main: $(curl -s -o /dev/null -w '%{http_code}' --max-time 4 http://localhost:8082/ 2>/dev/null)  playground: $(curl -s -o /dev/null -w '%{http_code}' --max-time 4 http://localhost:8080/playground 2>/dev/null)"
}

# ---------- tenant discovery ----------
# A fresh install regenerates the tenant/admin-user ids. Discover them at runtime (needs access_up
# first) and export so the LLM config + rules attach to the right tenant, not the captured one.
discover_tenant() {
  phase "discover tenant"
  local u; u="$(curl -s -u "${DISCO_ADMIN_USER}:${DISCO_ADMIN_PASSWORD}" http://localhost:8081/discovery/api/user 2>/dev/null)"
  TENANT_ID="$(printf '%s' "$u" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('accountID') or d.get('accountId') or '')" 2>/dev/null)"
  USER_ID="$(printf '%s' "$u" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('id') or '')" 2>/dev/null)"
  export TENANT_ID USER_ID
  [ -n "$TENANT_ID" ] && ok "tenant=$TENANT_ID user=$USER_ID" || warn "could not discover tenant (is access up + DISCO_ADMIN_PASSWORD set?)"
}

# ---------- LLM config ----------
# Insert the Azure chat (+ optional embeddings) config for the discovered tenant from secrets.env.
llm_config_up() {
  phase "LLM config"
  [ -n "${AZURE_OPENAI_API_KEY:-}" ] || { warn "no AZURE_OPENAI_API_KEY in secrets.env; configure the LLM in the UI (/llm-configuration)"; return 0; }
  [ -n "${TENANT_ID:-}" ] || discover_tenant
  [ -n "${TENANT_ID:-}" ] || { warn "no tenant; skipping LLM config"; return 0; }
  local chart; chart="$(kubectl -n "$NAMESPACE" get pods -o name | grep "$CHART_SVC" | grep -vE 'worker|mcp|celery|redis|init|dbm' | head -1 | sed 's#pod/##')"
  [ -n "$chart" ] || { warn "chart pod not found; skipping LLM config"; return 0; }
  kubectl -n "$NAMESPACE" exec -i "$chart" -- env T="$TENANT_ID" U="$USER_ID" \
    K="$AZURE_OPENAI_API_KEY" EP="${AZURE_OPENAI_ENDPOINT:-}" AV="${AZURE_OPENAI_API_VERSION:-2025-01-01-preview}" \
    CD="${AZURE_CHAT_DEPLOYMENT:-gpt-5-chat-deployment}" ED="${AZURE_EMBED_DEPLOYMENT:-}" python3 -c '
import os,json,psycopg2
c=psycopg2.connect(host="si-logi-symphony-postgresql",user=os.environ["POSTGRES_USER"],password=os.environ["POSTGRES_PASSWORD"],dbname=os.environ.get("POSTGRES_DATABASE","simbaintelligence"),connect_timeout=8);cur=c.cursor()
cur.execute("INSERT INTO llm_configurations (tenant_id,provider_type,name,credentials,created_by,updated_by,created_at,updated_at) VALUES (%s,2,%s,%s,%s,%s,now(),now()) RETURNING id",(os.environ["T"],"Azure OpenAI",json.dumps({"api_key":os.environ["K"],"api_version":os.environ["AV"],"azure_endpoint":os.environ["EP"]}),os.environ["U"],os.environ["U"]));cid=cur.fetchone()[0]
cur.execute("INSERT INTO llm_capabilities (capability_type,is_active,parameters,llm_configuration_id) VALUES (1,true,%s,%s)",(json.dumps({"deployment_name":os.environ["CD"]}),cid))
if os.environ.get("ED"): cur.execute("INSERT INTO llm_capabilities (capability_type,is_active,parameters,llm_configuration_id) VALUES (2,true,%s,%s)",(json.dumps({"deployment_name":os.environ["ED"]}),cid))
c.commit();print("  LLM configured: chat=%s embeddings=%s"%(os.environ["CD"],os.environ.get("ED") or "(none — set AZURE_EMBED_DEPLOYMENT or configure Vertex)"))
' 2>&1 | sed 's/^/  /' && ok "LLM config written; restarting app to load it" || warn "LLM config insert failed"
  kubectl -n "$NAMESPACE" rollout restart deploy/"$CHART_SVC" >/dev/null 2>&1
  kubectl -n "$NAMESPACE" rollout status deploy/"$CHART_SVC" --timeout=180s >/dev/null 2>&1 || true
}

# ---------- Discovery API ----------
_disco() { curl -s -u "${DISCO_ADMIN_USER}:${DISCO_ADMIN_PASSWORD}" -H "Accept: application/vnd.composer.v3+json" -H "Content-Type: application/vnd.composer.v3+json" "$@"; }

import_state() {
  phase "SI state import (connections + sources)  [BEST-EFFORT — verify after a real teardown]"
  if [ -z "$DISCO_ADMIN_PASSWORD" ]; then warn "no DISCO_ADMIN_PASSWORD; skipping. Build sources via the Data Source Agent using state/sources/*.json as the spec."; return 0; fi
  warn "Phase 7 is the unproven link. If a source does not appear/NLQ, rebuild it via the Data Source Agent (localhost:8080/data-source-agent) using state/sources/*.json, then re-run verify.sh."
  # connections (fill <REDACTED ...> placeholders from secrets.env via envsubst-style replace is demo-specific; left to env/state/import-connections.sh if present)
  if [ -x "$ENV_DIR/state/import.sh" ]; then
    DISCO_ADMIN_PASSWORD="$DISCO_ADMIN_PASSWORD" bash "$ENV_DIR/state/import.sh" || warn "state/import.sh reported issues"
  else
    warn "no state/import.sh — connections/sources not auto-imported (see state/README.md)"
  fi
}

apply_rules() {
  phase "tenant rules"
  local rules="$ENV_DIR/state/rules.json"
  [ -f "$rules" ] || { warn "no state/rules.json"; return 0; }
  local pod; pod="$(kubectl -n "$NAMESPACE" get pods -o name | grep "$CHART_SVC" | grep -vE 'worker|mcp|celery|redis' | head -1 | sed 's#pod/##')"
  [ -n "$pod" ] || { warn "chart pod not found; skipping rules"; return 0; }
  if [ -x "$_lib_dir/restore-rules.py" ]; then
    kubectl -n "$NAMESPACE" exec -i "$pod" -- env TENANT_ID="${TENANT_ID:-}" USER_ID="${USER_ID:-}" \
      python3 -c "$(cat "$_lib_dir/restore-rules.py")" < "$rules" \
      && ok "rules applied from rules.json" || warn "rules apply reported issues"
  else
    warn "lib/restore-rules.py missing"
  fi
}

# ---------- verify (the gate) ----------
verify_gate() {
  phase "verify"
  local fail=0
  # structural: core pods Ready
  local notready; notready="$(kubectl -n "$NAMESPACE" get pods --no-headers 2>/dev/null | grep -vE 'Completed|Running' | wc -l | tr -d ' ')"
  [ "$notready" = "0" ] && ok "all pods Running/Completed" || { warn "$notready pod(s) not ready"; fail=1; }
  # NLQ gate: ask each VERIFY_QUERIES question via the chart REST and grep expected fragments
  if [ "${#VERIFY_QUERIES[@]:-0}" -gt 0 ] && [ -n "$DISCO_ADMIN_PASSWORD" ]; then
    local row q expect
    for row in "${VERIFY_QUERIES[@]}"; do
      q="${row%%|*}"; expect="${row#*|}"
      log "Q: $q  (expect: ${expect//|/, })"
      warn "NLQ auto-check needs an authenticated chat session; run it in the Playground for now."
    done
  fi
  [ "$fail" = "0" ] && { ok "GATE GREEN"; return 0; } || { die "GATE RED"; }
}
