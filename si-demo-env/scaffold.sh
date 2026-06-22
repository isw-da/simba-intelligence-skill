#!/usr/bin/env bash
# Scaffold or refresh a demo's env/ from this engine.
#   scaffold.sh <target-repo-dir> <demo-name>   # create a new env/ (vendors lib)
#   scaffold.sh --sync <target-repo-dir>        # re-vendor lib/ into an existing env/
set -euo pipefail
SKILL="$(cd "$(dirname "$0")" && pwd)"

if [ "${1:-}" = "--sync" ]; then
  TARGET="${2:?usage: scaffold.sh --sync <target-repo-dir>}"
  ENVD="$TARGET/env"; [ -d "$ENVD" ] || { echo "no env/ in $TARGET"; exit 1; }
  rm -rf "$ENVD/lib"; cp -R "$SKILL/lib" "$ENVD/lib"
  echo "synced engine -> $ENVD/lib"; exit 0
fi

TARGET="${1:?usage: scaffold.sh <target-repo-dir> <demo-name>}"
NAME="${2:?usage: scaffold.sh <target-repo-dir> <demo-name>}"
ENVD="$TARGET/env"
mkdir -p "$ENVD"/{chart,data,edc,state/sources}
cp -R "$SKILL/lib" "$ENVD/lib"

# thin wrappers
for drv in up down verify; do
  cat > "$ENVD/$drv.sh" <<EOF
#!/usr/bin/env bash
ENV_DIR="\$(cd "\$(dirname "\$0")" && pwd)"; export ENV_DIR
exec bash "\$ENV_DIR/lib/$drv.sh" "\$@"
EOF
  chmod +x "$ENVD/$drv.sh"
done

cat > "$ENVD/config.sh" <<EOF
# Per-demo variables — the only file you must edit. See si-demo-env/README.md.
DEMO_NAME="$NAME"
NAMESPACE="si-${NAME##*-}"     # dedicated namespace = isolation
RELEASE="si"
CLUSTER="simba-intel-lab"      # blank = use current kube-context
EDCS=""                        # packaged EDCs to enable (comma-sep), reflected in values.yaml
CUSTOM_EDCS=""                 # custom EDC images in env/edc/ to build+load
HAS_DATA_TIER=true             # false for external-data demos
# install-specific IDs for rule import (discover with: SELECT tenant_id,user_id FROM rules LIMIT 1)
TENANT_ID=""
USER_ID=""
# the gate: "question|expected fragment|another fragment"
VERIFY_QUERIES=(
)
EOF

cat > "$ENVD/values.yaml" <<'EOF'
# SI Helm values for this demo. Enable the EDCs you need; keep ingress off for local.
ingress:
  enabled: false
discovery:
  edc:
    # saphana: { enabled: true }
    # oracle: { enabled: true }
    # hive: { enabled: true }
EOF

cat > "$ENVD/secrets.example.env" <<'EOF'
# Copy to secrets.env (GITIGNORED) and fill. Never commit secrets.env.
DISCO_ADMIN_USER=admin
DISCO_ADMIN_PASSWORD=
# add per-demo DB/LLM creds, e.g. ORACLE_PASSWORD=, AZURE_OPENAI_API_KEY=
EOF

cat > "$ENVD/state/README.md" <<'EOF'
# SI state as code
- `rules.json` — tenant rules snapshot (list).
- `sources/*.json` — exported source definitions.
- `connections.json` — connection definitions, secrets redacted.
- `import.sh` — OPTIONAL: recreates connections/sources via the Discovery API, filling
  redacted secrets from secrets.env. Best-effort until proven by a full teardown+rebuild.
EOF

cat > "$ENVD/data/README.md" <<'EOF'
# Data tier
k8s manifests (*.yaml) applied by up.sh, plus an optional `load.sh` that loads the tables.
Omit entirely for external-data demos (set HAS_DATA_TIER=false in config.sh).
EOF

# gitignore secrets in the target repo
GI="$TARGET/.gitignore"
grep -qxF 'env/secrets.env' "$GI" 2>/dev/null || printf '\n# si-demo-env secrets (never commit)\nenv/secrets.env\n' >> "$GI"

echo "scaffolded env/ in $TARGET"
echo "next: edit env/config.sh + env/values.yaml, add data/ + state/, then:"
echo "  cp $ENVD/secrets.example.env $ENVD/secrets.env && \$EDITOR $ENVD/secrets.env"
echo "  $ENVD/up.sh"
