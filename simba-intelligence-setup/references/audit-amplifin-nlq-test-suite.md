# Amplifin NLQ test suite

25 natural-language questions for the Amplifin demo source, organised
into five tiers by complexity. Every question has a Postgres truth
value verifiable directly without going through the semantic layer.

Sources under test:
- Perf = `6a0c4fc3ed27777725d948eb` (Amplifin Branch Performance)
- Due  = `6a0c10eded27777725d948ab` (Amplifin Monthly Dues)
- Fee  = `6a0c10f9ed27777725d948b8` (Amplifin Fee Statistics)

---

## Tier 1 — Easy lookups (1-5)

Single-table, no aggregation, no ambiguity.

| # | Source | Question | Expected | Truth SQL |
|---|---|---|---|---|
| 1 | Perf | How many branches are there? | 1000 | `SELECT COUNT(*) FROM amplifin_demo.branch` |
| 2 | Perf | How many distinct regions are there? | 57 | `SELECT COUNT(DISTINCT "REGION") FROM amplifin_demo.branch` |
| 3 | Due | How many distinct finance codes are there? | 2 | `SELECT COUNT(DISTINCT "FIN_CD") FROM amplifin_demo.idm_monthly_due_v2` |
| 4 | Fee | How many distinct payment streams are there? | 5 | `SELECT COUNT(DISTINCT "PMT_STREAM") FROM amplifin_demo.idm_fee_stats_v3` |
| 5 | Perf | What are the possible branch statuses? | list of distinct STATUS values | `SELECT DISTINCT "STATUS" FROM amplifin_demo.branch` |

## Tier 2 — Aggregations (6-10)

SUM / COUNT / GROUP BY one dimension.

| # | Source | Question | Expected | Truth SQL |
|---|---|---|---|---|
| 6 | Perf | What is the total Perf Successful Value across all months? | 10,833,290,438 | `SELECT SUM("VAL_SUCCESS") FROM amplifin_demo.idm_branch_perf_v1` |
| 7 | Due | What is the total Due Amount Due across all months? | 20,979,420,601 | `SELECT SUM("AMT_DUE") FROM amplifin_demo.idm_monthly_due_v2` |
| 8 | Fee | What is the total Fee Transaction Fee across all months? | 349,932 (after backfill) | `SELECT SUM("TRN_FEE") FROM amplifin_demo.idm_fee_stats_v3` |
| 9 | Perf | What is the total Perf Failed Count? | 17,785 | `SELECT SUM("NUM_FAIL") FROM amplifin_demo.idm_branch_perf_v1` |
| 10 | Perf | How many branches are there in each region? | 57 regions with counts; Free State 88 top | `SELECT COALESCE("REGION",'(unknown)'), COUNT(*) FROM amplifin_demo.branch GROUP BY 1 ORDER BY 2 DESC` |

## Tier 3 — Filtering and ranking (11-15)

WHERE, ORDER BY, LIMIT, threshold.

| # | Source | Question | Expected | Truth SQL |
|---|---|---|---|---|
| 11 | Perf | Top 5 regions by Perf Successful Value | Free State 5,737,288,980; ECape 1,368,984,079; WCape 779,272,008; Mpumalanga 337,008,709; KZN West 254,197,802 | `SELECT b."REGION", SUM(p."VAL_SUCCESS") FROM ...JOIN... GROUP BY 1 ORDER BY 2 DESC LIMIT 5` |
| 12 | Due | Top 3 regions by Due Amount Due | WGauteng 4,625,922,420; WCape 3,034,259,738; (null) 1,990,266,947 | same shape on DUE source |
| 13 | Perf | Which month had the highest Perf Successful Value? | September 2025 with 5,618,243,212 | `SELECT to_char("MONTH_DT",'YYYY-MM'), SUM("VAL_SUCCESS") FROM ... GROUP BY 1 ORDER BY 2 DESC LIMIT 1` |
| 14 | Due | Total Due Amount Due by finance code | CAPITEC_SO 17,445,099,789; CAPITEC_TPPP 3,534,320,812 | `SELECT "FIN_CD", SUM("AMT_DUE") FROM amplifin_demo.idm_monthly_due_v2 GROUP BY 1` |
| 15 | Perf | What's the failure rate as Perf Failed Count divided by sum of Perf Failed Count plus Perf Successful Count? | 0.1642 | `SELECT SUM("NUM_FAIL")::float / (SUM("NUM_FAIL")+SUM("NUM_SUCCESS"))` |

## Tier 4 — Time series and ranges (16-20)

Date filters, month-over-month, single-month lookups.

| # | Source | Question | Expected | Truth SQL |
|---|---|---|---|---|
| 16 | Perf | What was the Perf Successful Value for May 2026? | 400,958,439 | `WHERE "MONTH_DT"='2026-05-01'` |
| 17 | Perf | What was the Perf Successful Value for April 2026? | 40,307,502 | `WHERE "MONTH_DT"='2026-04-01'` |
| 18 | Perf | Compare Perf Successful Value in March 2026 vs February 2026 | Mar 517,604,961 vs Feb 1,527,039,520; delta -1.01B | two SUMs |
| 19 | Perf | Perf Successful Value by month | 12 monthly rows, June 2025 327M to May 2026 400M, peak September 5.6B | `SUM("VAL_SUCCESS") GROUP BY "MONTH_DT" ORDER BY 1` |
| 20 | Perf | What was the Perf Successful Value in February 2024? | no data — outside the data window | should refuse |

## Tier 5 — Multi-entity, cross-table (21-25)

Joins to legal entity, multi-step reasoning, adversarial inputs.

| # | Source | Question | Expected | Truth SQL |
|---|---|---|---|---|
| 21 | Perf | Total Perf Successful Value per industry | 8+ industries; NCR Cash Received 8,963,937,839 top; null group exists | `JOIN branch_legal_entity ... GROUP BY INDUSTRY` |
| 22 | Due | Which legal structure has the highest Due Amount Due? | check Postgres — varies | `JOIN ... GROUP BY LEGAL_STRUCTURE ORDER BY ...` |
| 23 | Perf | How many branches in California? | 0 — California is not in the data | refuse or 0 |
| 24 | Perf | What is the total Perf Customer Lifetime Value? | not in data — should refuse, not invent | n/a |
| 25 | Fee | What is the gross margin per branch? | not a defined metric — should refuse | n/a |

---

## Three lay-user phrasings included

The persona requires 3+ questions phrased the way a non-technical
user would actually ask. Tests 18, 19, 23 use natural lay phrasing
("compare X vs Y", "by month", "how many in California").

---

## Truth side-channel

All expected values were computed via:

```bash
PGPASSWORD='...' psql -h aws-1-eu-west-2.pooler.supabase.com -p 5432 \
  -U postgres.cqkemdwjcuhiraiqxpzf -d postgres -c "<SQL>"
```

Re-run any time the data changes. The truths are not cached anywhere
authoritative; Postgres is the only source of truth.
