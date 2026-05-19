# Amplifin audit triage

Findings from `audit-amplifin-qa-results.md` clustered by root cause,
with severity, blast radius, dependency, and recommended action.

---

## Cluster A: Source-picking happens before rules are consulted

**Root cause**: SI's chat agent selects which data source to query
based on field-label matching against the user's question, before any
tenant-wide rule is evaluated. The `sourceId` parameter is advisory
only.

**Blast radius**: Every question phrased without a source-specific
label (e.g. "what's the total amount") risks routing to the wrong
source. With 22 sources visible in the VDD tenant including FRC
`tx_amount`, the failure mode is reliable.

**Findings in this cluster**: AD-9, NR-10, NR-11

| Field | Value |
|---|---|
| Severity | CRITICAL |
| Layer | SI product (source-routing) |
| Effort | L (requires SI product change) |
| Blast radius | All bare-aggregate questions across all tenants |
| Dependency | SI product team |
| Action | File P1 product issue with reproduction. Workaround: prefix-led demo discipline. |

---

## Cluster B: LLM synthesises derived metrics from existing fields

**Root cause**: The LLM is willing to construct business metrics
(EBITDA, Customer Acquisition Cost, Net Profit Margin) by summing or
ratioing fields that have plausible names. The `no-synthesised-metrics`
rule sometimes fires, sometimes doesn't.

**Blast radius**: Every business metric outside the data model. High
risk because prospects often ask using their own internal vocabulary.

**Findings**: AD-7, AD-8

| Field | Value |
|---|---|
| Severity | CRITICAL |
| Layer | SI product (rule enforcement) + LLM stochasticity |
| Effort | M (better rules) + L (deterministic enforcement is product work) |
| Blast radius | Every synthesised metric, in every tenant |
| Dependency | SI product team for deterministic enforcement |
| Action | Strengthen the rule wording (done); demo brief should list "don't ask for X" metrics; product fix request |

---

## Cluster C: Partial dimension coverage on cross-table joins

**Root cause**: The chat agent's query planner returns a sampled or
limited dimension list rather than the full set when joining across
tables. 8 of 15 industries surface in `Total Perf Successful Value
per industry`.

**Findings**: CV-4

| Field | Value |
|---|---|
| Severity | MEDIUM |
| Layer | SI product (query planner) |
| Effort | M |
| Blast radius | Any "X by Y" question where Y is high-cardinality |
| Dependency | SI product team |
| Action | File issue. Workaround: state "Show all industries" explicitly in the question. |

---

## Cluster D: Phrasing-sensitive query plans

**Root cause**: The LLM constructs different query payloads depending
on whether a question uses "in May 2026", "for May 2026", "during May
2026", or "May 2026". Some forms apply the auto-injected time filter
correctly, others fail to.

**Findings**: BQ-3, BQ-5, RE-9

| Field | Value |
|---|---|
| Severity | MEDIUM |
| Layer | SI product (LLM tool-calling) |
| Effort | L |
| Blast radius | Single-month and recent-period questions |
| Dependency | SI product team |
| Action | Pre-verify each demo question's exact wording. Document working forms in the demo deck. |

---

## Cluster E: Aggregate value drift on "winner" queries

**Root cause**: "Which month had the highest X" returns the correct
month but a value 5.9% below the Postgres truth. Likely the planner
uses an approximate or sampled aggregation for max-finder queries.

**Findings**: RE-10

| Field | Value |
|---|---|
| Severity | LOW |
| Layer | SI product (query planner) |
| Effort | M |
| Blast radius | "Highest" / "lowest" / "best" / "worst" questions |
| Dependency | SI product team |
| Action | Workaround: ask "X by month" instead of "highest month" to get exact values. |

---

## Triage table

| finding_id | severity | root_cause_layer | cluster | effort | blast_radius | dependency | action |
|---|---|---|---|---|---|---|---|
| AD-7 | CRITICAL | SI product | B | L | every synthesised metric | SI product | strengthen rule + file P1 |
| AD-9 | CRITICAL | SI product | A | L | every bare-aggregate question | SI product | file P1 + prefix discipline |
| NR-10 | HIGH | SI product | A | L | same as AD-9 | SI product | covered by A |
| NR-11 | HIGH | SI product | A | L | same as AD-9 | SI product | covered by A |
| AD-8 | HIGH | LLM stochasticity | B | L | non-deterministic synthesis | SI product | covered by B |
| CV-4 | MEDIUM | SI product | C | M | high-cardinality groupby | SI product | file issue |
| BQ-3 | MEDIUM | SI product | D | L | recent-period questions | SI product | document working forms |
| BQ-5 | MEDIUM | SI product | D | M | this-vs-last-month patterns | SI product | covered by D |
| RE-10 | LOW | SI product | E | M | highest-X queries | SI product | document workaround |
| RE-9 | LOW | SI product | D | L | "in May 2026" wording | SI product | covered by D |

---

## Recommended fix order

### Phase 1 (before Wed/Thu Amplifin call)

1. **Audience briefing.** Tell Freddy + team to lead every NLQ with
   "Perf", "Due", or "Fee". This works around Cluster A (the
   CRITICAL leak) without waiting on product. Dependency: none.

2. **Pre-verified question deck.** The 25 questions in the test
   suite, with their exact passing phrasing. Hand-curated so every
   question on the deck has been observed to return the right
   answer ≥ 3 times. Dependency: existing test suite.

3. **Rule-set commit.** The 13 rules in Rules Management are
   captured. Commit them to git as code so they survive a tenant
   re-build. Dependency: none.

### Phase 2 (post-Amplifin call, before next demo)

4. **Cluster A: P1 product issue.** Reproduction:
   "Question 'what's the total amount?' with `sourceId =
   <Amplifin Fee Statistics>` returns 153B from FRC's tx_amount."
   Asks: respect sourceId as scope, not advisory.
   Dependency: SI product team.

5. **Cluster B: P1 product issue.** Reproduction:
   "Question 'what is the EBITDA?' returns a fabricated number
   built from cost_* fields, despite a rule forbidding synthesis."
   Asks: enforce rules at the planning step, not just the
   response-formatting step.
   Dependency: SI product team.

### Phase 3 (when product fixes land)

6. **Cluster C, D, E.** File the lower-severity issues. Each is a
   query-planner refinement.

---

## Notes

Two of the CRITICAL findings (AD-7, AD-9) cannot be fully closed at
the semantic-layer level. The audit is honest about this. A 90% pass
rate is achievable today with audience briefing; 95% requires
product fixes; 100% will likely require a fundamental change to the
chat agent's source-routing layer.
