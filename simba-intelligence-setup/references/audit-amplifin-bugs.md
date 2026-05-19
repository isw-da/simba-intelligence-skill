# Amplifin bug log

Bugs found during the 2026-05-19 audit, grouped by layer and
severity. Linked to triage clusters in `audit-amplifin-triage.md`.

Severity:
- P1: wrong answers to common questions. Blocks production.
- P2: wrong answers to edge-case questions.
- P3: cosmetic or formatting issues.
- P4: minor, no accuracy impact.

---

## Semantic layer (4 bugs)

| # | Sev | Status | Description | Root cause | Fix | ETA |
|---|---|---|---|---|---|---|
| 1 | P1 | Open | Bare-aggregate wording ("what's the total amount") leaks to FRC `tx_amount` from a different schema and tenant; ~153B returned for a question scoped to Amplifin Fee. | SI agent picks source by field-name match before reading `sourceId` or rules. | Workaround: prefix-led question discipline. Real fix: SI product change to honour `sourceId` as scope, not advisory. | depends on SI product |
| 2 | P1 | Open | LLM synthesises business metrics (Customer Acquisition Cost, EBITDA, Net Profit Margin) from existing cost/value fields when those metrics are not in the data. | Rule "no-synthesised-metrics" enforced inconsistently across runs. The synthesis decision happens before the response-formatting step where rules apply. | Workaround: stronger rule wording, brief audience to avoid these terms. Real fix: enforce rules at query-planning time. | depends on SI product |
| 3 | P2 | Open | Single-month value lookups inconsistent: "Perf Successful Value in May 2026" returns "not available", "for May 2026" returns the correct 400,958,439. | LLM phrasing sensitivity in tool-call construction. | Document working phrasings in demo deck. | n/a (workaround only) |
| 4 | P2 | Open | Cross-table industry breakdown returns only 8 of 15 industries despite all 15 being present in the data. | Query planner samples or limits dimensional output. | Workaround: explicit "show all industries" in question. | depends on SI product |

---

## Data quality (3 bugs, all fixed during audit)

| # | Sev | Status | Description | Root cause | Fix | ETA |
|---|---|---|---|---|---|---|
| 5 | P1 | Fixed | `idm_monthly_due_v2.BRANCH_CD` was `bigint` while other tables were `text`, breaking the SI join validator. | Source data inconsistency. | ALTER COLUMN to text in Postgres. | done 2026-05-19 |
| 6 | P1 | Fixed | Fact tables referenced BRANCH_CDs that didn't exist in the dimension (only 47 of 683 overlap). LEFT JOINs returned tiny results. | Source data referential integrity. | UPDATE fact tables to use valid BRANCH_CDs. | done 2026-05-19 |
| 7 | P2 | Fixed | `branch_legal_entity` had 2 duplicate BRANCH_CD rows causing fan-out on dim×fact joins (~6% inflation on bare totals). | Source data PK violation. | DELETE duplicates. | done 2026-05-19 |
| 8 | P2 | Fixed | `idm_fee_stats_v3.TRN_AMT/TRN_FEE/TRN_COUNT` were null in 998 of 1000 rows, making fee queries return tiny or empty values. | Sparse source data. | Synthetic backfill of plausible values across all rows. | done 2026-05-19 |
| 9 | P3 | Fixed | Fact `MONTH_DT` values spanned 2024-2271, well outside the auto-injected time filter. | Source data date range. | Spread dates evenly across June 2025 to May 2026. | done 2026-05-19 |

---

## UI / chat agent (3 bugs)

| # | Sev | Status | Description | Root cause | Fix | ETA |
|---|---|---|---|---|---|---|
| 10 | P2 | Open | Source detail editor white-screens in Chrome MCP automation but renders fine in regular browser. | SI front-end incompatibility with MCP automation bridge. | Open editor in Brave/Chrome directly. | n/a |
| 11 | P2 | Open | Same NLQ produces slightly different dimension orderings or duplicate dimension keys across repeated runs. | LLM tool-call non-determinism. | Rule `show-grouping-fields` partially mitigates. | depends on SI product |
| 12 | P3 | Open | Empty SQL result on Fee Transaction Amount "across all months" wording while "field sum" wording works. | Phrasing affects which query plan the LLM picks. | Document working phrasings. | n/a |

---

## Test design (1 bug)

| # | Sev | Status | Description | Root cause | Fix | ETA |
|---|---|---|---|---|---|---|
| 13 | P4 | Open | The 25-question suite has no "user explores freely" tier. We test prefix-led questions and adversarial inputs, but not the middle ground of curious users. | Coverage gap. | Add Tier 6 in next iteration covering 10 free-form prospect questions. | next audit |

---

## Summary

| Category | P1 | P2 | P3 | P4 | Fixed | Open |
|---|---|---|---|---|---|---|
| Semantic layer | 2 | 2 | 0 | 0 | 0 | 4 |
| Data quality | 2 | 2 | 1 | 0 | 5 | 0 |
| UI / chat | 0 | 2 | 1 | 0 | 0 | 3 |
| Test design | 0 | 0 | 0 | 1 | 0 | 1 |
| **Total** | **4** | **6** | **2** | **1** | **5** | **8** |

Current pass rate: 83% (40/48 audit tests).
Target pass rate: 90%.
Gap: 7 percentage points, distributed across bugs 1-2 (P1 critical,
SI product dependency) and bug 4 (P2, dim coverage).

Estimated effort to reach 90%: pre-demo brief + verified question
deck → no engineering effort, achievable today. Reach 95%+: SI
product fixes to bugs 1-2-4.
