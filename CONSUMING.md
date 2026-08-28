# Using this repo, and the others alongside it

These repositories are a shared knowledge base for insightsoftware's Logi Composer, Simba
Intelligence and Logi Report. They are maintained by Amin Hasan and anyone on the team is
welcome to clone, pin, fork or open an issue against them.

## The set

| Repo | What it holds | Refresh |
|---|---|---|
| [`isw-da/logi-si-docs`](https://github.com/isw-da/logi-si-docs) | Documentation mirror: SI, Composer v25 and v26, the legacy devnet archive, and the Composer OpenAPI specs | **Automatic**, weekly |
| [`isw-da/composer-mcp`](https://github.com/isw-da/composer-mcp) | Composer REST API as MCP tools, with guards, plus the reference docs | Manual |
| [`isw-da/simba-intelligence-skill`](https://github.com/isw-da/simba-intelligence-skill) | SI install, configuration and troubleshooting skills | Manual |
| [`isw-da/symphony-dashboard-builder-skill`](https://github.com/isw-da/symphony-dashboard-builder-skill) | Building Composer dashboards server side, and the client-side assembly around them | Manual |
| [`isw-da/simba-intelligence-mcp`](https://github.com/isw-da/simba-intelligence-mcp) | SI API as MCP tools (private) | Manual |
| [`isw-da/logi-report-kb`](https://github.com/isw-da/logi-report-kb) | Logi Report and JReport documentation and API surface (private) | Manual |

## Pin a version, do not track a branch

Every repo cuts tagged releases. The default branch moves, sometimes several times a day,
and it moves because something turned out to be wrong. Pin unless you want that.

```bash
git clone --branch v0.3.0 --depth 1 https://github.com/isw-da/simba-intelligence-skill.git
```

Release notes name what changed and, where it matters, what was found to be **wrong** in the
previous version. That second part is the useful one.

## What this repo holds

Four skills (each with a `SKILL.md`), two script toolkits, and one worked use case. All
of it is instructions and scripts rather than a running service. Copy the checkout into `~/.claude/skills/`, or point any LLM session at the
`SKILL.md` you need.

| Directory | What it is for |
|---|---|
| `simba-intelligence-setup/` | Installing, configuring and troubleshooting SI on kind, EKS, AKS, GKE, on-prem and air-gapped. Thirty-four reference guides, plus install scripts for macOS, Windows and Linux |
| `si-analytics-agent/` | Turning an SI deployment into an analytics agent, with the validation steps that stop it answering confidently from nothing |
| `nlq-testing/` | Adversarial QA for a natural-language-query build, before a number goes in front of anyone |
| `edc-connector-testing/` | Test plan for an Enterprise Data Connector |
| `demo-prep/` | The narrated walkthrough video pipeline: annotate screens, generate narration, stitch a synced mp4 |
| `si-demo-env/` | Scaffolding a throwaway SI demo environment, with a Caddy gateway in front |
| `use-cases/debit-order-payments/` | One worked use case end to end: data shape, derived fields, tenant rules, question bank, demo flow |

The `universal/simba-intelligence-llm-guide.md` file is the same setup knowledge written for
LLM clients that are not Claude.

## How to trust what you read here

One gate, runnable from a fresh clone with no Kubernetes, no SI and no network:

```bash
python3 verify-skill.py
echo $?                 # on its own line: a pipe reports the pipe's status, not the gate's
```

It runs four named checks and prints each one: every `SKILL.md` parses with a `name` and a
`description` (without them the skill never loads), every tracked Python script compiles,
every tracked shell script parses under `bash -n` (an install script that fails on syntax
fails on somebody else's machine, which is the worst place to find out), and every citation
that unambiguously points inside this repo resolves. It was proved by breaking it: the
citation check found a guide pointing at `simba-intelligence-setup/scripts/apply_rules.py`,
a script that does not exist, and went red until that was fixed.

Some checks report **NOT APPLICABLE** rather than passing or failing. That means the thing
they check is real but not present in your checkout. A skip is always named and counted,
never silent, and the gate fails if a check in the manifest does not run at all.

If a gate is red, the documentation is wrong, not the gate.

## What is deliberately not here

- **No cluster, no credentials, no kubeconfig.** Every script takes a host and a key as
  arguments. Nothing here authenticates anywhere by itself, and no secret is committed.
- **No customer names, deployed customer artefacts, or NDA-tagged material.** The
  `use-cases/debit-order-payments/` data shape is synthetic and modelled on a pattern, not
  copied from a deployment.
- **No SI product source, and no Helm chart.** Those come from insightsoftware's own
  distribution. This repo tells you how to drive them.
- **No demo assets.** `demo-assets/` is gitignored: video, audio and screen captures are
  large, they rot, and they usually carry somebody's screen.

If you spot something that should not be public, say so and it comes out the same day.

## Contributing

Open an issue or a pull request. Two asks:

1. **Run the gates before you open it.** If your change makes a claim, the gate should be
   the thing that proves it, and if no existing check covers your claim, add one.
2. **Say how you know.** A file and line, a command and its output, a Confluence page id or
   a Jira key. "I believe" is fine as long as it says so; the corpus already contains several
   confident claims that turned out to be wrong, and each one cost somebody a day.
