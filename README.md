# Simba Intelligence skills

Skills that guide an LLM through installing, configuring, testing and demoing **Simba
Intelligence** (SI) on any Kubernetes environment. Written for Claude Code, and usable from
ChatGPT, Gemini or any other client through `simba-intelligence-setup/universal/simba-intelligence-llm-guide.md`.

Repo: https://github.com/isw-da/simba-intelligence-skill

## Who it is for

Anyone at insightsoftware who has to stand SI up, keep it up, or show it working: solution
engineers building a demo environment, support and services staff debugging a customer
install, and anyone testing whether an NLQ answer can be trusted.

## What is in it

| Directory | What it is for |
|---|---|
| `simba-intelligence-setup/` | Install, configure and troubleshoot SI on kind, EKS, AKS, GKE, on-prem and air-gapped, with install scripts for macOS, Windows and Linux |
| `si-analytics-agent/` | Turn an SI deployment into an analytics agent, with the validation that stops it answering confidently from nothing |
| `nlq-testing/` | Adversarial QA for a natural-language-query build, before a number goes in front of anyone |
| `edc-connector-testing/` | Test plan for an Enterprise Data Connector |
| `demo-prep/` | The narrated walkthrough video pipeline: annotate screens, generate narration, stitch a synced mp4 |
| `si-demo-env/` | Scaffold a throwaway SI demo environment behind a Caddy gateway |
| `use-cases/debit-order-payments/` | One worked use case end to end: data shape, derived fields, tenant rules, question bank, demo flow |
| `mcp-server/` | A small MCP server that serves the setup guides and install scripts to Claude Desktop as tools, so the reference content does not have to be uploaded by hand |

## Using it

Pin a tag rather than tracking `main`:

```bash
git clone --branch v0.3.0 --depth 1 https://github.com/isw-da/simba-intelligence-skill.git
```

Then either copy the directories you want into `~/.claude/skills/`, or point a session at the
relevant `SKILL.md`. Start with `simba-intelligence-setup/SKILL.md` if you are installing.

**[`CONSUMING.md`](CONSUMING.md)** has the full picture: how to pin, how to run the gate,
what is deliberately not in here, and how to contribute.

## Checking it before you trust it

```bash
python3 verify-skill.py
echo $?
```

Five named checks, all runnable from a fresh clone with no cluster and no network: skill
frontmatter carries the keys it needs, the frontmatter loads as YAML, Python compiles, shell
parses, and every repo-internal citation resolves. `pyyaml` is optional; without it the parse
check reports NOT APPLICABLE by name rather than passing quietly. Every tagged release runs
the gate before the release is cut.

## See also

Other Logi Composer / Simba Intelligence developer toolkit components in the same org:

- [`isw-da/symphony-dashboard-builder-skill`](https://github.com/isw-da/symphony-dashboard-builder-skill):
  Claude skill for building Composer dashboards programmatically.
- [`isw-da/composer-mcp`](https://github.com/isw-da/composer-mcp): MCP
  server wrapping the Composer REST API as tools (sources, visuals,
  dashboards, accounts, trusted access tokens).
- [`isw-da/simba-intelligence-mcp`](https://github.com/isw-da/simba-intelligence-mcp):
  the SI API as MCP tools. Private.
- [`isw-da/edc-graphql`](https://github.com/isw-da/edc-graphql): Java
  Enterprise Data Connector that lets Simba Intelligence query any GraphQL
  API.
