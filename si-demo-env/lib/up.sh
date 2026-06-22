#!/usr/bin/env bash
# Engine up-driver. Invoked by a demo's thin env/up.sh (which exports ENV_DIR).
# Idempotent: safe to re-run. Stops on hard failures, warns on best-effort phases.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

load_config
load_secrets
preflight
ensure_namespace
prereqs               # PVCs + Oracle ojdbc driver — BEFORE helm (else the EDC hangs --wait)
helm_up
wait_ready
custom_edcs_build
secrets_to_k8s
data_tier_up
access_up
discover_tenant      # fresh install regenerates the tenant id; discover it for LLM/rules
llm_config_up        # Azure chat (+ optional embeddings) from secrets.env
import_state          # BEST-EFFORT — connections scriptable; SOURCES need the Data Source Agent
apply_rules
verify_gate

printf '\n%s%s is up.%s  Open http://localhost:8080/playground\n' "$CG" "$DEMO_NAME" "$C0"
printf 'Tear down with: %s/down.sh\n' "$ENV_DIR"
