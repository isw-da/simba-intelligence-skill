# si-demo-env — the standard for reproducible Simba Intelligence demo environments

> **26.3 (unreleased): phase 2 of this scaffold assumes the SI chart shape.**
> Phase 2 runs `helm install`/`helm upgrade` from a vendored `chart/`, implemented
> at `lib/common.sh`. Every demo repo that has vendored a copy of `lib/` carries
> the same assumption, so a 26.3 demo environment is not a matter of changing this
> repo alone.
>
> From 26.3, Simba Agentic Intelligence ships as a sub-component of the Logi
> Composer Helm chart (PY-693) and the standalone `simba-intelligence-chart`
> is deprecated (PY-701). A separate SI chart pointing at a Composer hosted
> elsewhere is recorded as no longer supported in 26.3 and later (Confluence
> page 18711380170). SI also moves off the root path to
> `{composer-context}/intelligence`, and signs users in through Composer
> rather than through its own login (PY-689).
>
> Nothing below has been re-tested against 26.3 and no 26.3 replacement is
> written here, because the transition guide (PY-706) was unfinished when this
> note was added. 26.3 was unreleased at that point, so treat all of it as
> subject to change. See `../simba-intelligence-setup/references/si-26.3-notes.md`.

The way every SI demo or PoV is packaged so it can be spun up, torn down, and
deployed anywhere from its own git repo. The engine lives here in the skill; each
demo repo **vendors** a copy of `lib/` so it stays self-contained.

## Why
SI demos accumulate live state (connections, sources, rules, data, LLM config) that
otherwise lives only in a cluster and gets lost or collides with other demos. This
standard captures that state as code, behind two commands: `up.sh` and `down.sh`.

## The contract: every demo repo has an `env/`
```
env/
  config.sh           # per-demo variables (the ONLY file you must edit per demo)
  values.yaml         # SI Helm values (which EDCs to enable, ingress off)
  chart/              # vendored SI Helm chart tarball (OCI pull is broken; pin the version)
  data/               # OPTIONAL in-cluster data tier: k8s manifests + load scripts
  edc/                # OPTIONAL custom EDC images to build + load (build context or Dockerfile)
  state/              # SI as code:
    connections.json  #   connection definitions, secrets redacted (filled from secrets.env)
    sources/*.json    #   exported source definitions
    rules.json        #   tenant rules snapshot
  secrets.example.env # committed template of required secrets
  secrets.env         # REAL secrets — GITIGNORED, never committed
  lib/                # vendored engine (do not edit; refresh with `scaffold sync`)
  up.sh               # thin wrapper -> lib/up.sh
  down.sh             # thin wrapper -> lib/down.sh
  verify.sh           # thin wrapper -> lib/verify.sh (the gate)
```

You customise `config.sh`, `values.yaml`, `data/`, `state/`, `secrets.example.env`.
Everything in `lib/` is identical across demos.

## config.sh — the per-demo variables
```bash
DEMO_NAME="vodafone-turkey"        # used in messages
NAMESPACE="si-turkey"              # dedicated namespace -> full isolation, no cross-demo collisions
RELEASE="si"                       # helm release name
CLUSTER="simba-intel-lab"          # kind cluster (or leave blank to use current kube-context)
EDCS="oracle,hive"                 # which packaged EDCs to enable in values.yaml
CUSTOM_EDCS="oracle-telco"         # custom EDC images from env/edc/ to build+load (or "")
HAS_DATA_TIER=true                 # false for external-data demos (e.g. Group on SAP)
# the gate: question -> expected answer fragment(s), tab-separated
VERIFY_QUERIES=(
  "What is the ARPU in EUR by region?|Anatolia|Marmara"
)
```

## up.sh phases (all idempotent)
1. preflight: tools present, cluster reachable, secrets.env exists
2. namespace + helm install/upgrade from `chart/` with `values.yaml`
3. data tier: `kubectl apply` `data/` + run its load scripts (skipped if `HAS_DATA_TIER=false`)
4. custom EDC images: build + `kind load` each in `CUSTOM_EDCS`
5. secrets: create k8s secrets from `secrets.env` (never from git)
6. access: port-forwards + Caddy gateway on :8080
7. state: import `state/connections.json` (+ secrets) and `state/sources/*.json` via Discovery API
8. rules: apply `state/rules.json`
9. verify: run `verify.sh` (the gate)

## Honesty / known limits
- **Secrets are never committed.** The repo is "deploy anywhere" *given the operator
  supplies `secrets.env`*. Recipe is contained; credentials are not.
- **External-data demos can't spin up their data.** A demo whose data is a live
  external system (e.g. SAP Datasphere/HANA Cloud) sets `HAS_DATA_TIER=false`; `up.sh`
  stands up SI + the connection recipe, not the data.
- **State import (phase 7) is the unproven link.** Data tier, helm, secrets, access and
  rules are reliable. Recreating connections/sources from JSON via the API is best-effort
  until proven by a full teardown-and-rebuild. Until then `up.sh` prints a clear fallback:
  rebuild the source via the Data Source Agent using `state/sources/*.json` as the spec.
- **One at a time on a laptop.** A full SI stack is ~15 pods; on 32 GB run one namespace
  at a time. Namespaces make that switch clean (`down.sh` one, `up.sh` the other).

## Create a new demo
From the skill: `si-demo-env/scaffold.sh <target-repo-dir> <demo-name>` drops a stub `env/`
with the engine vendored. Then fill `config.sh`, `values.yaml`, `data/`, `state/`,
`secrets.example.env`, copy `secrets.example.env` to `secrets.env`, fill it, and run
`env/up.sh`.

## Refresh the engine in an existing demo
`si-demo-env/scaffold.sh --sync <target-repo-dir>` re-vendors `lib/` from the skill.
