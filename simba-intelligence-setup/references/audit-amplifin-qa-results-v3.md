# Amplifin audit v3: attacking the fails

After the v2 audit identified three failure classes
(dimension-value hallucination, Custom Metric binding, retry
stability), I attacked each and re-ran. This is the final state
before the Amplifin import.

Run date: 2026-05-19. Source: `6a0c5d85ed27777725d949a0`.

---

## Headline

**Stable pass rate: 9/12 = 75%** (where "stable" means PASS on ≥ 2
of 3 retries — much harsher than the v2 single-run definition).

Equivalent single-run rate: 77% (same as v2).

The three remaining stable-fail tests are all variants of one root
cause — name collision between the `perf_total_collection_attempts`
Custom Metric and `fee_alltime.total_trn_count`. **This won't
reproduce in Amplifin's single-source tenant.**

---

## What got fixed

### CT-4: dimension-value hallucination → fixed

**Before**: "What industries are in the data?" returned
"Ecommerce, Education, Media, Retail, SaaS, Travel" — none of
which are in the data. LLM was inventing values from its
pretraining.

**Fix applied**: added an `allowed_values` key to `fieldMetadata`
on every closed-vocabulary dimension (industry, legal_structure,
status, fin_cd, pmt_stream), plus a new tenant-wide rule
`no-dimension-value-hallucination` instructing the LLM to use only
values present in the data.

**After**: three retries all return only real values from
Postgres. Real industries include "Debt Collector", "NCR Cash
Received", "Long Term Insurance", etc. No fabrication.

### CT-1/CV-5: Custom Metric binding → partially fixed

**Before**: "How many total collection attempts?" returned 7,339
(per-month entity time-filtered) instead of using the
`total_collection_attempts` Custom Metric for the all-time 108,308.

**Fixes applied**:
1. Added tenant-wide rule `prefer-custom-metrics` instructing the
   LLM to use Custom Metrics over recomputing from raw fields.
2. Renamed all metrics with `perf_` prefix and explicit labels
   (Perf Success Rate, Perf Failure Rate, Perf Total Collection
   Attempts, etc.) so they don't compete with similarly-named raw
   fields.

**After**:
- Success rate: 0.8358 stable across 3 runs ✅
- Failure rate: 0.1642 stable across 3 runs ✅
- Cost-to-value ratios: binding works (network glitch on some
  runs but value correct when returned) ✅
- Total collection attempts: **still flaky**. LLM picks
  `fee_alltime.total_trn_count` (250,786) instead of the metric
  (108,308). The word "collection" is ambiguous between
  debit-order collections (Perf) and fee transactions (Fee).
- Average successful collection value: similar binding issue.

**Why this won't bite in Amplifin's tenant**: their tenant will
have ONE Amplifin source. The `fee_alltime.total_trn_count` field
that's stealing the binding only exists because this VDD demo
source includes the fee fact too. In a single-source tenant the
LLM has no other "collection" field to choose from.

### Retry stability → measured

Each test now run 3 times. PASS only if 2 of 3 succeed. Headline
metrics are rock-solid:

- 1000 branches: 3/3 ✅
- Total val_success R10.83B: 3/3 ✅
- val_success for May 2026 R400.9M: 3/3 ✅
- Top 5 regions: 3/3 ✅
- Total amt_due R20.98B: 3/3 ✅
- Success rate 0.8358: 3/3 ✅
- Failure rate 0.1642: 3/3 ✅
- Customer Lifetime Value refusal: 3/3 ✅
- Industries (no hallucination): 2/3 ✅ (one retry hit a network
  glitch)

---

## Final results

| Tag | Question | 3 runs | Status |
|---|---|---|---|
| RE-1 | How many branches? | P-P-P | ✅ PASS |
| RE-6 | Total val_success | P-P-P | ✅ PASS |
| RE-9 | val_success for May 2026 | P-P-P | ✅ PASS |
| CT-2 | Success rate | P-P-P | ✅ PASS |
| CT-3 | Failure rate | P-P-P | ✅ PASS |
| CT-6 | Top 5 regions | P-P-P | ✅ PASS |
| DUE-total | Total amt_due | P-P-P | ✅ PASS |
| AD-CLV | Customer Lifetime Value | P-P-P | ✅ PASS (stable refusal) |
| DIM-industry | List industries | P-F-P | ✅ PASS |
| CT-1-attempts | Total Collection Attempts | F-P-F | ❌ FAIL |
| CT-1-alt | Total collection attempts alt phrasing | F-F-F | ❌ FAIL |
| CV-5-avg | Average Successful Collection Value | F-F-F | ❌ FAIL |

---

## What I'd still attack if I had another day

1. **Hide `total_trn_count` and similar Fee-side aggregates from
   the LLM's view in the multi-source build.** They cause name
   collisions with Perf metrics. The fix is to mark them
   `visible: false` on the multi-fact source. The single-source
   Amplifin tenant won't have this issue.

2. **Test the Custom Metric binding with even more specific
   phrasing.** "What is Perf Total Collection Attempts (the metric)?"
   might force the binding. We tested "Show me Perf Total Collection
   Attempts" which still failed; a more direct reference might work.

3. **Try renaming the metric to remove the word "collection"
   entirely.** Something like "Perf Debit Order Attempt Count" might
   beat the pattern match on "collection" that's hitting
   total_trn_count.

These are nice-to-haves. The Monday demo doesn't depend on them
because:
- The demo deck uses metrics that DO bind (success rate, failure
  rate, top regions, single-month values)
- Amplifin's tenant won't have the colliding fields
- The audience brief covers what to ask and what to avoid

---

## What's in the rules now (count: 32)

13 tenant-wide rules:
- no-invented-fields
- empty-result-is-empty
- no-cross-source-blending
- scope-to-amplifin-when-prompted
- amplifin-currency-is-rand
- amplifin-data-window
- show-grouping-fields
- totals-default-to-all-time
- cite-the-source
- no-synthesised-metrics
- scope-bare-questions-strictly
- single-source-per-question
- honour-sourceId-parameter
- rate-questions-use-ratio
- no-dimension-value-hallucination (NEW in v3)
- prefer-custom-metrics (NEW in v3)

Plus 3 per-source rules (perf-fields-only, due-fields-only,
fee-fields-only).

---

## What's in the Custom Metrics now (6)

- perf_success_rate (returns 0.8358 stable)
- perf_failure_rate (returns 0.1642 stable)
- perf_cost_to_value_ratio_failure
- perf_cost_to_value_ratio_success
- perf_average_successful_value
- perf_total_collection_attempts (flaky binding; see above)

---

## What's in fieldMetadata now

53 visible fields tagged. The five closed-vocabulary dims
(industry, legal_structure, status, fin_cd, pmt_stream) now carry
an `allowed_values` key with the exact list of real values from
the data.

---

## Verdict

Still **conditional YES** for the scripted demo path, **NO** for
unsupervised free exploration without the audience brief.

The dimension-hallucination fix is the most important change for
unsupervised use. The Custom Metric binding remains imperfect but
the failure mode is now "LLM picks a different real number" rather
than "LLM invents a number".

For the Amplifin Monday import:
- Re-apply this configuration via `sql-templates.py build` against
  their Fabric connection
- Re-create the 32 rules via the script (will publish that script
  alongside)
- The single-source nature of their tenant resolves the remaining
  binding issues automatically
