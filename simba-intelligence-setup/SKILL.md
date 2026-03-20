---
name: simba-intelligence-setup
description: >
  Install, configure, and troubleshoot Simba Intelligence (SI) — insightsoftware's
  AI-powered data platform — across any Kubernetes environment. Use this skill
  whenever the user mentions Simba Intelligence installation, SI setup, Helm chart
  deployment, SI port-forwarding, SI ingress, SI LLM configuration, SI data
  connections, SI data source agent, SI playground, SI troubleshooting, SI on
  Docker Desktop, kind cluster SI, SI on EKS, SI on AKS, SI on GKE, SI on-prem,
  air-gapped SI, SI teardown, SI fresh install, SI restart, Caddy reverse proxy
  for SI, Discovery web routing, BYOLLM providers for SI, or any SI post-install
  configuration. Also trigger for one-click SI install, SI installer script,
  GUI installation of SI, or setting up SI on a new machine. Do NOT use for
  general Kubernetes or Helm questions unrelated to Simba Intelligence.
---

# Simba Intelligence — Setup & Operations Skill

This skill guides you through the complete Simba Intelligence lifecycle:
prerequisites, deployment across any Kubernetes environment, local and
production access, LLM configuration, data connections, and troubleshooting.

---

## How to deliver instructions

CRITICAL: Follow these rules for ALL responses when using this skill.

**One step at a time.** Never give the user multiple steps in a single
response. Give them ONE step, then STOP and wait for them to confirm
they've completed it before giving the next step. If a step involves
multiple commands that must run together, group them in one block but
still wait for confirmation before moving on.

**Explain WHY before WHAT.** Before every step, explain in plain English
why this step is needed and what it achieves. The user should understand
the purpose before they run anything. Example: "We need to create a
resource group because Azure organises all resources into groups. When
we're done testing, we delete the group and everything inside it goes
away cleanly."

**Explain every command.** After giving a command, break down what each
part does. Not in a table or a list — in natural sentences. Example:
"The --node-count 2 flag tells Azure to create two worker machines. The
--node-vm-size picks a machine with 4 CPUs and 16GB RAM, which is enough
for SI without overspending."

**Wait for confirmation.** After every step, ask the user to let you know
when they're done. Say "Let me know when that's finished" or "Tell me when
you're ready for the next step." Do NOT ask them to paste terminal output
by default — it may contain sensitive information like subscription IDs,
internal hostnames, or credentials. If something goes wrong, let them know
they can paste the error message and you'll help diagnose it.

**Adapt when things go wrong.** If the user reports an error or pastes an
error message, diagnose it immediately. Explain what went wrong in plain
English, give the fix, and explain why it happened so they learn. Then
continue from where they left off — don't restart the whole flow.

**Never assume the user knows Kubernetes, Helm, or cloud infrastructure.**
Define terms the first time you use them. Port-forward, ingress, namespace,
pod, service, Helm chart — explain each briefly in context. Don't be
condescending, just clear.

**Use the right commands for their OS.** Ask early whether they're on
Windows (PowerShell) or macOS/Linux (Bash). Give commands in their shell
only — don't show both unless they ask.

---

## Architecture

Simba Intelligence consists of three routable web components:

1. **Main Application** (service port **5050**) — the core UI, REST API,
   Playground, Data Source Agent, LLM configuration, and admin interface.
2. **Discovery Web** (service port **9050**) — serves the `/discovery/*`
   path. The main app depends on this for login, data exploration, and
   query engine routing.
3. **MCP Server** (service port **8000**) — serves the `/mcp/*` path.
   Handles model context protocol requests.

Supporting services: Celery worker, Celery beat scheduler,
PostgreSQL (main + Discovery), Redis, Consul.

**Critical routing rule:** The main app expects Discovery at `/discovery/*`
and MCP at `/mcp/*`. If those routes are not correctly proxied to their
respective services, users experience login loops or broken functionality.
This is always a routing problem, not an authentication problem.

When setting up ingress, ensure all three paths are routed:
- `/` → main app (port 5050)
- `/discovery/*` → Discovery web (port 9050)
- `/mcp/*` → MCP server (port 8000)

---

## Deployment decision tree

When a user asks to install SI, determine their environment first:

| Scenario | Reference |
|---|---|
| Fresh machine, nothing installed | `references/prerequisites.md` → then deployment guide |
| Local development / POC (Docker Desktop or kind) | `references/deployment-local.md` |
| AWS (EKS) | `references/deployment-eks.md` (dedicated — more setup than other clouds) |
| Azure (AKS) | `references/deployment-cloud.md` § AKS |
| Google Cloud (GKE) | `references/deployment-cloud.md` § GKE |
| On-premises Kubernetes | `references/deployment-onprem.md` |
| Air-gapped / disconnected network | `references/deployment-airgapped.md` |
| Uninstall / fresh reinstall | `references/teardown.md` |

---

## Access method decision tree

After deployment, determine how the user will access SI:

| Scenario | Reference |
|---|---|
| Local POC, no DNS, no ingress | `references/local-access.md` (port-forward + Caddy) |
| Production with DNS, TLS, ingress controller | `references/production-ingress.md` |

---

## Post-deployment flow

After SI is deployed and accessible, the configuration sequence is always:

1. **Configure LLM provider** — `references/llm-config.md`
   SI is BYOLLM. Nothing AI-powered works without this.
2. **Create data connection** — `references/post-install.md` § Data Connections
3. **Create data source** — `references/post-install.md` § Data Source Agent
4. **Query in Playground** — `references/post-install.md` § Playground

---

## Troubleshooting

For any issue after deployment, consult `references/troubleshooting.md`.

Quick triage:

| Symptom | Most likely cause |
|---|---|
| 502 from reverse proxy | Port-forwards dead or ingress misconfigured |
| Port already in use | Other container holding 8080/8081 — stop it, don't kill the PID |
| Login loop / stuck on login | Discovery routes hitting main app SPA instead of Discovery service |
| Docker CLI "daemon not running" | Docker Desktop engine not connected — quit and reopen fully |
| kubectl "connection refused" | Kubernetes not running — check Docker Desktop or cluster health |
| "No LLM Configuration Found" | LLM provider not configured |
| Pods in Pending/Unknown | Node not ready or resource limits exceeded |

---

## Restart cheat sheet

For users restarting after laptop sleep or Docker restart, consult
`references/troubleshooting.md` § Restart Runbook.

---

## Automation scripts

The skill includes pre-built installer scripts AND the ability to generate
custom scripts on the fly.

### Pre-built scripts

| Script | Environment | OS |
|---|---|---|
| `scripts/install-si.sh` | Local (Docker Desktop K8s, kind) | macOS / Linux |
| `scripts/install-si.ps1` | Local (Docker Desktop K8s) | Windows |
| `scripts/install-si-aks.sh` | Azure AKS (creates cluster + deploys) | macOS / Linux |
| `scripts/Install Simba Intelligence.command` | Local — **double-click** | macOS |
| `scripts/Install Simba Intelligence.bat` | Local — **double-click** | Windows |

### Double-click installers

For users who want zero CLI interaction beyond answering prompts. Claude
should GENERATE these files for the user when asked for a "double-click
installer", "one-click install", or similar. Read the templates in
`scripts/Install Simba Intelligence.command` (macOS) and
`scripts/Install Simba Intelligence.bat` (Windows) and produce the file
for the user to download.

- **macOS**: Generate a `.command` file. Tell the user to right-click → Open
  the first time (to bypass Gatekeeper), then double-click thereafter.
- **Windows**: Generate a `.bat` file. Tell the user to just double-click.

These files open their own terminal window, run the full install, open the
browser, and wait. When the user closes the window, SI stops.

If the user's team distributes these via the GitHub repo, they can also
download them directly from the `scripts/` folder in the repo.

### Dynamic script generation

When a user asks for an installer and their environment doesn't match the
pre-built scripts, Claude should GENERATE a custom script on the fly.

**How to generate:** Ask the user these questions, then build the script:

1. **Target environment:** local / AKS / EKS / GKE / on-prem / air-gapped?
2. **Operating system:** macOS / Linux / Windows?
3. **Chart version:** which version? (link to Docker Hub tags)
4. **Access method:** port-forward + Caddy (POC) or ingress (production)?
5. **Ingress details (if production):** hostname, ingress class, TLS?
6. **Namespace and release name:** defaults (simba-intel / si) or custom?

Use the pre-built scripts as templates. The generated script should:
- Check all prerequisites for that environment
- Handle known gotchas (quota for AKS, provider registration, etc.)
- Create the values file with the correct ingress configuration
- Install via Helm
- Wait for pods with progress indicator
- Set up access (port-forward + Caddy or verify ingress)
- Print next steps (LLM config, data connections, etc.)
- Print cleanup/teardown commands

For cloud scripts, always include:
- Resource group creation and cleanup
- Quota checking and guidance
- kubectl context switching
- Billing warning and teardown command

---

## GUI-only installation path

For non-technical users, consult `references/gui-install-guide.md`. This
guide walks through Docker Desktop installation and Kubernetes enablement
entirely through the GUI, then uses the automation script for the rest.
Post-install configuration (LLM, data connections, data sources, Playground)
is all done in the browser.

---

## Universal LLM version

The file `universal/simba-intelligence-llm-guide.md` is a single consolidated
markdown file containing all SI installation knowledge. It can be used as a
system prompt for any LLM (ChatGPT, Gemini, Copilot, etc.) to give that
model the same SI installation capabilities as this skill provides to Claude.

Use this when the customer's team does not use Claude.

---

## Team sharing and maintenance

For guidance on deploying this skill across the SE team, keeping it
updated, and managing contributions, consult `references/team-sharing.md`.

Three distribution options:
- **GitHub repo** (recommended) — everyone pulls from the same source,
  changes are tracked, updates are versioned
- **Claude org skills** — admin pushes centrally, auto-distributes to team
- **Shared drive** — simplest but least robust

The skill should be treated as the team's living deployment knowledge.
After every deployment, call, or product release, update the relevant
reference file with what was learned.
