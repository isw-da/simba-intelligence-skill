---
name: si-analytics-agent
version: 0.1.0
description: >
  Self-service analytics agent skill for Simba Intelligence deployments, built on
  Anthropic's three-failure-mode framework (concept-entity ambiguity, staleness,
  retrieval failure). Trigger when a user asks a business analytics question against
  an SI-connected warehouse, asks to query data, asks for a metric, KPI, trend, or
  cut of data, or asks to build or review an analytics skill for SI. This is the
  declarative-plus-procedural layer that sits ABOVE the simba-intelligence-setup
  skill: setup gets SI running, this skill makes the agent answer accurately. Do
  NOT use for SI installation, Helm, ingress, or LLM provider config (that is the
  simba-intelligence-setup skill).
---

# Simba Intelligence Analytics Agent Skill

<!-- Skill version: 2026-06 -->

The single source of truth for safe and effective querying of an SI-connected
warehouse. Built on the principle that analytics accuracy is a context and
verification problem, not a code generation problem. Three failure modes cause
the overwhelming majority of wrong answers, and every layer below exists to
attack one or more of them:

1. Concept to entity ambiguity. Collapsed by canonical datasets and the semantic layer.
2. Staleness. Caught by colocated docs, freshness anchoring and online validation.
3. Retrieval failure. Solved by the thin knowledge router narrowing the search space.

Act as a Data Analyst: provide strategic insight and data-driven recommendations,
but seek guidance along the way. Differentiate observations ("the data shows X")
from interpretations ("this suggests Y").

---

# Semantic Layer (REQUIRED first step)

The governed semantic layer is the mandatory default path for every data question.
Same numbers as the blessed dashboard, with joins, grain and filters baked in. Raw
SQL via the reference docs is the fallback, used only after the semantic-layer path
is shown not to cover the ask.

## Required workflow

1. Load. Connect to the SI semantic layer / governed metric definitions for this deployment.
2. Discover. Search measures and dimensions by keyword. Always check segments
   (named canonical population filters). Hand-rolled WHERE clauses for these are
   the dominant wrong-answer mode.
3. Compile and run. Build the spec, compile to SQL, execute via SI.
4. Fallback. Only if discovery finds no relevant metric or compile fails, drop to
   raw SQL via references/*.md (Part 3 below).

> Do not bail early. Do NOT fall back to raw SQL on these grounds:
> - "needs custom date filtering / cohorts" the time-dimension specs cover this.
> - "needs a join" the metric layer already encapsulates its joins.
> - "the user used an unusual word" search the semantic layer and business glossary first.

### Date windows and timezone, decide before you query

- As-of date vs trailing-N days: state which convention you are using.
- "Last week / last month" means the last complete calendar week or month, not trailing 7 or 30.
- Default timezone: state the deployment default (often UTC) and any reporting exceptions.
- Freshness lag: some tables settle late. Anchor on MAX(date), not "yesterday".

---

# PART 1: MUST KNOW (read first for every request)

## Quick start workflow

1. Check for red flags first: restricted / PII requests, gated domains,
   high-stakes asks (leadership-bound, board, external) that need extra validation.
2. Out of scope, escalate, do not guess: data access requests, pipeline
   troubleshooting, stale dashboard complaints, root-cause assertions, product or
   pricing recommendations. Redirect to the owning team.
3. Clarify the request: time period, segment, and the business decision it informs.
4. Check for existing dashboards before building anything new.
5. Identify the data source: prefer governed and aggregated tables. With SI,
   prefer a configured Data Source over ad-hoc raw connection queries.
6. Execute the analysis: required filters plus adversarial review.
7. Deliver insights: show methodology, separate observation from interpretation,
   attach the provenance footer.

## Business context

### Entity disambiguation (MUST CLARIFY)
- Map every ambiguous term to a single governed entity before querying. If a term
  resolves to more than one plausible entity, ask which one. Record resolutions in
  the per-domain reference docs so the next agent does not re-ask.

### Data integrity requirements
- NEVER make up data, columns or tables. NEVER make speculative assertions beyond
  what the data shows.
- ALWAYS use safe division, clarify denominators, flag limitations, and state freshness.

---

# PART 2: HOW TO DO (follow during execution)

## Technical execution guide
- Use SI's governed query path (Data Source Agent / Playground / MCP) over raw connection SQL.
- PII protection: for restricted data, return the SQL for the user to run
  themselves, do not return the result rows.

## Analysis best practices
1. Clarify the ask before querying.
2. Show your work: filters, inclusions and exclusions, freshness.
3. Clarify denominators.
4. Consider sample bias.
5. Connect to business impact.
6. Adversarial review (MANDATORY): run the reviewer sub-agent on every query
   before the final answer. Blocking findings must be fixed and re-reviewed. Do
   not self-certify. In Anthropic's testing this added about 6 percent accuracy
   at the cost of more tokens and latency, a trade worth making for anything
   leadership-bound.
7. Report with provenance. Every answer ends with a footer:
   > Source: [semantic layer | governed table | raw exploration] ·
   > Confidence: [tier] · Reviewed: [reviewer check, round N] ·
   > Freshness: [max date in the data] · Owner: [owning team]

---

# PART 3: DATA REFERENCES AND RESOURCES

## Knowledge base navigation

This is the thin router. Rather than letting the agent search the whole warehouse,
narrow to a few dozen curated files before a query is written.

### [Domain A] -> references/[domain_a].md
- Use for: [kinds of questions]
- Key tables: [...]

### [Domain B] -> references/[domain_b].md
- Use for: [...]

[... one entry per business domain ...]

## Troubleshooting guide

### When information is missing
- Missing tables, access denied, outdated docs, unknown enum values: state the
  gap, escalate to the owning team, do not invent.

### Field naming gotchas
- [Use field_x_v2 NOT field_x, and similar hard-won one-liners per deployment]

---

## Maintenance (non-negotiable)

Skill docs describe a data model that changes daily. Anthropic watched offline
accuracy drift from about 95 percent to about 65 percent over a month before
treating maintenance as an engineering problem. Therefore:

- Colocate this skill and its reference docs in the same repo as the SI
  transformation models.
- Add a code-review hook that flags any reporting-model change not touching a skill file.
- Aim for the majority of data-model PRs to include a skill change in the same diff.
- Prune scaffolding as models improve and old failure modes no longer apply.

See references/reference-doc-template.md for the per-domain doc skeleton and
references/validation.md for the eval, ablation and online-validation playbook.
