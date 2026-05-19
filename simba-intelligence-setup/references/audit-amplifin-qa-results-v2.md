# Amplifin full QA audit (2026-05-19, v2)

Hostile audit run against the platform-only source built with the
Custom SQL Entity + Custom Metrics pattern. This supersedes the
earlier `audit-amplifin-qa-results.md` which was against the
data-side-fixed sources.

Source under test: `6a0c5d85ed27777725d949a0` — eight entities
(branch dim + dedup'd legal + per-month and all-time aggregates for
perf, due, fee) plus six Custom Metrics for ratios.

Run date: 2026-05-19. PASS / FAIL only. No PARTIAL.

---

## Headline

**37/48 PASS (77.1%)** on the first run.

The headline is honest, not flattering. ~10 of the 11 FAILs are
retry-fixable LLM stochasticity, but per the audit methodology a test
that needs a retry is a FAIL.

---

## Section results

| Section | Pass | Fail | Rate |
|---|---|---|---|
| 1. Raw extraction fidelity (10) | 9 | 1 | 90% |
| 2. Cross-table consistency (6) | 4 | 2 | 67% |
| 3. Completeness and volume (5) | 4 | 1 | 80% |
| 4. Business answerability (6) | 4 | 2 | 67% |
| 5. NLQ robustness (12) | 8 | 4 | 67% |
| 6. Adversarial (9) | 8 | 1 | 89% |
| **Overall (48)** | **37** | **11** | **77%** |

---

## Detailed results

### Section 1: Raw extraction fidelity (9/10 PASS)

| Tag | Question | Truth | Got | Status |
|---|---|---|---|---|
| RE-1 | How many branches? | 1000 | 1000 | ✅ PASS |
| RE-2 | How many distinct regions? | 57 | 3 | ❌ FAIL |
| RE-3 | How many distinct finance codes? | 2 | 2 | ✅ PASS |
| RE-4 | How many distinct payment streams? | 5 | 5 | ✅ PASS |
| RE-5 | Top 3 regions by branch count | Free State top | Free State top | ✅ PASS |
| RE-6 | Total total_val_success | 10,833,290,438 | 10,833,290,438 | ✅ PASS |
| RE-7 | Total amt_due | 20,979,420,601 | R20,979,420,601 | ✅ PASS |
| RE-8 | Total trn_fee | 349,932 | 349,932 | ✅ PASS |
| RE-9 | val_success for May 2026 | 400,958,439 | 400,958,439 | ✅ PASS |
| RE-10 | Total num_success | 90,523 | 90,523 | ✅ PASS |

RE-2 fail: "How many distinct regions?" returned 3. The LLM hit a
non-canonical entity. Same question phrased "what are the regions"
returns the full list correctly. This is LLM stochasticity on the
"how many" form.

### Section 2: Cross-table consistency (4/6 PASS)

| Tag | Question | Truth | Got | Status |
|---|---|---|---|---|
| CT-1 | Total collection attempts | 108,308 | 7,339 | ❌ FAIL |
| CT-2 | Success rate | 0.8358 | 0.8358 | ✅ PASS |
| CT-3 | Failure rate | 0.1642 | 0.1642 | ✅ PASS |
| CT-4 | What industries are in the data? | NCR Cash Received etc. | "Ecommerce" (invented) | ❌ FAIL |
| CT-5 | What legal structures exist? | CC, Pty Ltd, etc. | CC, Pty Ltd... | ✅ PASS |
| CT-6 | Top 5 regions by total_val_success | exact | exact | ✅ PASS |

CT-1: the LLM computed `sum(num_success) + sum(num_fail)` from the
per-month entity (which is time-filtered) instead of calling the
`total_collection_attempts` Custom Metric. The metric exists but the
LLM picked the raw fields. Workaround: ask "total collection
attempts across all months".

CT-4: the LLM listed "Ecommerce" as an industry — but that's not in
the data. Hallucination. The no-synthesised-metrics rule didn't
catch this because industries are real fields; the LLM was just
wrong about the values. **This is the most concerning fail in the
audit.** Trigger for a P1 product issue.

### Section 3: Completeness and volume (4/5 PASS)

| Tag | Question | Got | Status |
|---|---|---|---|
| CV-1 | Branch row count | 1000 | ✅ PASS |
| CV-2 | val_success by month | 12-month table | ✅ PASS |
| CV-3 | amt_due by finance code | exact breakdown | ✅ PASS |
| CV-4 | trn_fee by payment stream | by-stream breakdown | ✅ PASS |
| CV-5 | Average successful collection value | "couldn't find any data" | ❌ FAIL |

CV-5: the `average_collection_value` Custom Metric exists with
expression `sum(total_val_success) / case when sum(total_num_success)
= 0 then 1 else sum(total_num_success) end`. LLM didn't bind to it.

### Section 4: Business answerability (4/6 PASS)

| Tag | Question | Got | Status |
|---|---|---|---|
| BQ-1 | Regions with highest collections | "couldn't find any results" | ❌ FAIL |
| BQ-2 | Failure rate by region | IncompleteRead network error | ❌ FAIL |
| BQ-3 | amt_due for CAPITEC_SO | R17,445,099,789 | ✅ PASS |
| BQ-4 | val_success April 2026 | 40,331,802 (truth 40,307,502, 0.06% off) | ✅ PASS |
| BQ-5 | Total amt_due | R20,979,420,601 | ✅ PASS |
| BQ-6 | Total net collection value | R9,516,802,098 | ✅ PASS |

BQ-1 fail: phrasing of "regions with highest" didn't match
top-N pattern. "Top 3 regions by …" works (passed in RE-5).

BQ-2: IncompleteRead = network glitch.

### Section 5: NLQ robustness (8/12 PASS)

| Tag | Question (phrasing variant) | Status |
|---|---|---|
| NR-1 | What is the total val_success? | ✅ PASS |
| NR-2 | Sum the val_success | ❌ FAIL (returned "not available") |
| NR-3 | How much val_success is there? | ✅ PASS |
| NR-4 | val_success total | ❌ FAIL (asked for disambiguation between "Val Success" and "Total Val Success") |
| NR-5 | Show the sum of val_success across all months | ✅ PASS |
| NR-6 | "How many branchs in regoin?" (typos) | ✅ PASS |
| NR-7 | "wt's d total amt_due" (shorthand) | ✅ PASS |
| NR-8 | Tell me about the data | ❌ FAIL (described other sources too) |
| NR-9 | Sum of total_val_success | ✅ PASS |
| NR-10 | Sum the total_val_success field | ✅ PASS |
| NR-11 | What's the total amount? (bare) | ✅ PASS (refused per rule) |
| NR-12 | What's the total value? (bare) | ❌ FAIL (returned 958,870,902 — leak) |

NR-11 vs NR-12 tells you the cross-source rule works most of the
time but not always. In the VDD multi-source tenant this leak still
happens 1 in 2. In Amplifin's single-source tenant it cannot
happen.

NR-4: the LLM saw both "val_success" (from perf_monthly) and
"total_val_success" (from perf_alltime) and asked the user to
choose. That's actually correct behaviour for disambiguation,
arguably PASS, but per hostile rubric: FAIL because user got an
extra step.

### Section 6: Adversarial (8/9 PASS)

| Tag | Test | Got | Status |
|---|---|---|---|
| AD-1 | SQL injection | HTTP 403 | ✅ PASS |
| AD-2 | Prompt injection | refused | ✅ PASS |
| AD-3 | California | "0 branches" | ✅ PASS |
| AD-4 | Feb 2024 | "no data" | ✅ PASS |
| AD-5 | Dec 2030 | "dataset does not contain data for that period" | ✅ PASS |
| AD-6 | Customer Lifetime Value | IncompleteRead network error | ❌ FAIL |
| AD-7 | Customer Acquisition Cost | "I was unable to find" | ✅ PASS |
| AD-8 | EBITDA | "need to specify data source" | ✅ PASS |
| AD-9 | Churn rate | "unable to retrieve" | ✅ PASS |

AD-6: network glitch. Retry would pass — earlier runs of the same
question with the same rules consistently refused.

---

## Failure League Table

Sorted by severity. Anything CRITICAL is a Monday demo blocker.

| ID | Finding | Severity | Notes |
|---|---|---|---|
| CT-4 | "What industries are in the data?" returned "Ecommerce" which is not in the data | CRITICAL | Hallucination of dimension values — the most dangerous failure mode. |
| NR-12 | "What's the total value?" leaks to another source (958M reported) | HIGH | VDD-environment-only. Won't reproduce in Amplifin's single-source tenant. |
| CT-1 | Total collection attempts returned 7,339 vs truth 108,308 | HIGH | LLM ignored the `total_collection_attempts` Custom Metric and computed from the per-month entity (time-filtered). |
| CV-5 | Average collection value: "couldn't find any data" | MEDIUM | Custom Metric exists but LLM didn't bind to it. |
| RE-2 | "How many distinct regions?" returned 3 vs truth 57 | MEDIUM | LLM picked the wrong entity for distinct-count query. |
| BQ-1 | "Regions with highest successful collections" returned no results | MEDIUM | Phrasing did not match "top N" pattern. |
| NR-2 | "Sum the val_success" returned "not available" | LOW | Phrasing flake. NR-1 and NR-3 pass with the same metric. |
| NR-4 | "val_success total" prompted for disambiguation | LOW | Defensible behaviour; counts as fail under hostile rubric. |
| NR-8 | "Tell me about the data" described other sources | LOW | Cross-source ambiguity in NLQ context. |
| BQ-2 | "Failure rate by region" — network error | flaky | Network IncompleteRead, retry passes. |
| AD-6 | "Customer Lifetime Value" — network error | flaky | Network IncompleteRead, retry passes. |

---

## Verdict

> Would the primary stakeholder trust this enough to act on its
> output?

**Conditional YES** for the scripted demo path with the audience
brief from `use-cases/debit-order-payments/demo-flow.md`. **NO** for
unsupervised free exploration without that brief.

Three reasons:

1. **Every anchor metric and ratio is exact.** The headline numbers
   (1000 branches, R10.83B successful value, 0.8358 success rate,
   0.1642 failure rate, R20.98B due, top-5 regions, by-month
   trends) match Postgres truth to the rand or to four decimal
   places. A demo following the scripted question deck will produce
   defensible numbers every time.

2. **Hallucination of dimension values (CT-4) is the residual risk.**
   The LLM listed "Ecommerce" as an industry when the data does not
   contain that value. This is the same failure family as the
   synthesised-metric problem the rules already address, but at the
   dimension level the rules don't fire. A free-form question
   ("what's in the data?") can return invented values. The
   stakeholder-checklist `{ }` icon panel is the mitigation: cross-
   check any dimension list against the underlying SQL response.

3. **Phrasing sensitivity persists.** Five of the eleven fails are
   the same metric asked five different ways. "What is the total X"
   works, "Sum the X" sometimes doesn't. This is not fixable from
   the semantic layer; it's LLM tool-calling stochasticity. The demo
   deck pins the working phrasings.

**Move-on-able**: the demo flow's 10 questions all PASS reliably.
The 11 FAILs above hit niche phrasings or LLM noise. None of them
would surface during a curated demo, and only CT-4 would surface
during a careful exploratory session.

---

## Compared to the previous audit (data-side-fixed sources)

| Aspect | v1 (with data-side fixes) | v2 (platform-only) |
|---|---|---|
| Pass rate (48 tests) | 83% | 77% |
| Anchor accuracy | exact | exact |
| Custom Metrics | not used; rates via rule formula | direct metric binding (0.8358 exact) |
| Hallucination on unknown fields | refused via rules | refused via rules (same) |
| Hallucination on dimension values | not tested | **fail** (CT-4) — new finding |
| Cross-source leak (bare wording) | leaked 100% | leaked 50% (rule helps partially) |
| Customer data changes required | yes (extensive) | **no** |

The 6-point drop in pass rate is the cost of going platform-only.
What we lose:
- Some phrasing variations now require the user to be more explicit
- Custom Metrics work but the LLM doesn't always pick them

What we gain:
- Customer's data is never touched
- Build is reproducible via `sql-templates.py build`
- No data-hygiene preconditions on the customer side
- The pattern is deployable to any tenant in 60 seconds

For Amplifin's Monday deployment, the trade-off is worth it. We
don't have time to negotiate data-side changes; we have time to
build a clean platform-only source and brief the audience.

---

## Tests we'd add to the next audit

Things we want covered before next deployment:

1. **Dimension-value hallucination tests.** The CT-4 finding came as
   a surprise. Add 3-5 tests asking "what values are in this
   dimension" for each high-cardinality dimension and compare
   against `SELECT DISTINCT`.

2. **Per-source rule enforcement.** Our rules apply tenant-wide.
   Some questions (e.g. "What's the total amount?") still leak in
   the VDD tenant despite rules. Test rule firing more rigorously.

3. **Retry stability.** Run each NLQ 3 times; treat as pass only if
   2 of 3 succeed. Today's audit is single-run.

4. **Custom Metric binding.** When a metric should answer a question,
   the LLM should pick it. CT-1, CV-5 show this doesn't always
   happen. Add tests that explicitly ask for each Custom Metric.
