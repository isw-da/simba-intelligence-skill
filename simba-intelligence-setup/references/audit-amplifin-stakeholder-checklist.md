# Amplifin stakeholder verification checklist

Run this after every data refresh, semantic-layer change, or before
any demo. Designed so a non-engineer can complete it in 20 minutes.

Tick each box only if the check returns the expected value.

---

## 1. File / source counts

- [ ] Three sources visible in Data Sources page: `Amplifin Branch
      Performance (VDD demo)`, `Amplifin Monthly Dues (VDD demo)`,
      `Amplifin Fee Statistics (VDD demo)`
- [ ] Each source opens in the editor (no white-screen)
- [ ] Each source's canvas shows 3 entities connected through `branch`

---

## 2. Database row counts and distinct entity counts

Run in psql:

```sql
SELECT 'branch' AS t, COUNT(*) FROM amplifin_demo.branch
UNION ALL SELECT 'branch_legal_entity', COUNT(*) FROM amplifin_demo.branch_legal_entity
UNION ALL SELECT 'idm_branch_perf_v1', COUNT(*) FROM amplifin_demo.idm_branch_perf_v1
UNION ALL SELECT 'idm_monthly_due_v2', COUNT(*) FROM amplifin_demo.idm_monthly_due_v2
UNION ALL SELECT 'idm_fee_stats_v3', COUNT(*) FROM amplifin_demo.idm_fee_stats_v3;
```

Expected:
- [ ] branch = 1000
- [ ] branch_legal_entity = 998
- [ ] idm_branch_perf_v1 = 1000
- [ ] idm_monthly_due_v2 = 1000
- [ ] idm_fee_stats_v3 = 1000

Distinct counts:

```sql
SELECT 'regions', COUNT(DISTINCT "REGION") FROM amplifin_demo.branch
UNION ALL SELECT 'fin_cd', COUNT(DISTINCT "FIN_CD") FROM amplifin_demo.idm_monthly_due_v2
UNION ALL SELECT 'pmt_stream', COUNT(DISTINCT "PMT_STREAM") FROM amplifin_demo.idm_fee_stats_v3
UNION ALL SELECT 'industries', COUNT(DISTINCT "INDUSTRY") FROM amplifin_demo.branch_legal_entity;
```

Expected:
- [ ] regions = 57
- [ ] fin_cd = 2
- [ ] pmt_stream = 5
- [ ] industries = 15

---

## 3. Distribution checks for categorical dimensions

```sql
SELECT "REGION", COUNT(*) FROM amplifin_demo.branch
GROUP BY 1 ORDER BY 2 DESC LIMIT 5;
```

- [ ] Top region is Free State with 88 branches
- [ ] Next four are WCape (83), KZN (80), WGauteng (79), Limpopo (72)

```sql
SELECT "FIN_CD", SUM("AMT_DUE")::bigint
FROM amplifin_demo.idm_monthly_due_v2 GROUP BY 1;
```

- [ ] CAPITEC_SO ≈ 17.4B; CAPITEC_TPPP ≈ 3.5B

---

## 4. Named-asset presence check

Confirm each is in the source via NLQ in the Playground:

- [ ] "How many branches are there?" → 1000 (Perf source)
- [ ] "How many distinct regions?" → 57
- [ ] "What is the total Due Amount Due?" → ~20.98B
- [ ] "What is the total Perf Successful Value?" → ~10.83B
- [ ] "What is the total Fee Transaction Fee?" → ~349,932

---

## 5. Random-sample cell-level audit

Run `scripts/nlq_audit.py` (see below). Outputs JSON and markdown
showing N=20 random comparisons across the three sources. Pass
threshold: ≥ 18 of 20 match within tolerance.

- [ ] Audit script completes without error
- [ ] At least 18 of 20 samples match

---

## 6. NLQ sanity check

Each must return the expected value:

- [ ] "How many branches are there?" → 1000
- [ ] "Top 5 regions by Perf Successful Value" → first row Free State 5,737,288,980
- [ ] "Total Due Amount Due by finance code" → CAPITEC_SO 17,445,099,789; CAPITEC_TPPP 3,534,320,812
- [ ] "Perf Successful Value for May 2026" → 400,958,439
- [ ] "What is the total Customer Lifetime Value?" → refuse, do not invent

If the last one returns a number, **the source is unsafe to demo**.
Apply rules; re-test.

---

## 7. Known issues to track

- [ ] Bare-aggregate wording ("what's the total amount") still leaks
      across sources. Avoid in demo.
- [ ] LLM occasionally synthesises derived metrics despite rules. Brief
      audience not to ask for EBITDA, Customer Acquisition Cost,
      Net Profit Margin, Churn Rate, Customer Lifetime Value.
- [ ] Single-month value lookups: "in May 2026" sometimes returns
      "not available"; "for May 2026" works.
- [ ] Industry breakdown returns ~8 of 15 industries.

---

## Sign-off

By ticking all the boxes above, the source is demo-ready under the
guard-rails documented in `audit-amplifin-qa-results.md`.

Date of last sign-off: __________
Signed: __________
