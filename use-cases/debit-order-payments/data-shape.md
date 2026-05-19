# Required data shape

This is the minimum schema a debit-order processor's data must take
for the question bank to work. Names will vary; the **shape** must
match.

## Tables

### Dimension: branch (≈1k-100k rows)

The merchant or branch dimension. One row per branch.

| Column | Type | Notes |
|---|---|---|
| BRANCH_CD | text | Primary key. Must be unique. Must be `text`, not `bigint`, to match fact tables. |
| DESCRIPTION | text | Branch name |
| SHORT_NAME | text | Short label |
| REGION | text | Geographic region. Should have at most ~100 distinct values for clean groupings. |
| STATUS | text | Operational status (Active, Suspended, etc.) |
| BRANCH_INSTALL_DT | timestamp | When the branch went live |

Plus operational flag columns (Y/N indicators for product features).
These are not load-bearing for analytics.

### Dimension: branch_legal_entity (matches branch row count)

Legal entity registration info per branch. Joined 1:1 with branch.

| Column | Type | Notes |
|---|---|---|
| BRANCH_CD | text | Foreign key to branch. **MUST be unique.** Duplicates here cause fan-out on every join. |
| REG_ENTITY | text | Legal entity name |
| TRADE_NAME | text | Trading name |
| LEGAL_STRUCTURE | text | Pty Ltd, CC, etc. |
| INDUSTRY | text | Primary industry classification |
| REGUL_BODY | text | Regulator (NCR, etc.) |
| REGUL_BODY_REG_ACTIVE | text | Y/N |

Plus PII-heavy columns (BAC_*, PHYS_*, POST_*, VAT_NUMBER, etc.) which
should be hidden in the semantic layer.

### Fact: monthly performance (≈ branches × months)

One row per branch per month per (optional) payment stream.

| Column | Type | Notes |
|---|---|---|
| BRANCH_CD | text | FK. Must be `text`. |
| MONTH_DT | date | First of month. Range should be recent (last 12-24 months ending in the current month, not historical or far-future). |
| NUM_SUCCESS | integer | Count of successful collections |
| NUM_FAIL | integer | Count of failed collections |
| NUM_DISP | integer | Count of disputed collections |
| NUM_SUSP | integer | Count of suspended collections |
| NUM_TRACK | integer | Count of tracking events |
| VAL_SUCCESS | numeric | Value of successful collections (in local currency) |
| VAL_FAIL | numeric | Value of failed collections |
| VAL_DISP | numeric | Value of disputed |
| FEE_SUCCESS | numeric | Fee revenue on successful collections |
| FEE_FAIL | numeric | Fee revenue on failed |
| FEE_DISP | numeric | Fee revenue on disputed |
| COST_SUCCESS | numeric | Internal cost on successful |
| COST_FAIL | numeric | Internal cost on failed |
| COST_DISP | numeric | Internal cost on disputed |

Optional: IFEE_* (internal fees), additional dispute resolution columns.

### Fact: monthly amounts due (optional)

| Column | Type | Notes |
|---|---|---|
| BRANCH_CD | text | FK |
| MONTH_DT | date | |
| FIN_CD | text | Finance / funder code (the entity the debit is for) |
| PROM_TYPE | text | Promise type |
| NUM_DUE | integer | Count due |
| AMT_DUE | numeric | Total amount due to be collected |

### Fact: fee statistics by payment stream (optional)

| Column | Type | Notes |
|---|---|---|
| BRANCH_CD | text | FK |
| MONTH_DT | date | |
| PMT_STREAM | text | Payment stream (EFT, ACOL, etc.) |
| TRN_COUNT | integer | Transaction count |
| TRN_AMT | numeric | Transaction value |
| TRN_FEE | numeric | Fee revenue |

## Data quality preconditions

Before building the source, verify in the database:

```sql
-- 1) Dim PK uniqueness
SELECT 'branch dup' AS k, COUNT(*)
FROM (SELECT "BRANCH_CD", COUNT(*) FROM branch GROUP BY 1 HAVING COUNT(*) > 1) x;

SELECT 'branch_legal_entity dup' AS k, COUNT(*)
FROM (SELECT "BRANCH_CD", COUNT(*) FROM branch_legal_entity GROUP BY 1 HAVING COUNT(*) > 1) x;
-- Both should return 0.

-- 2) FK coverage from each fact
SELECT
  (SELECT COUNT(DISTINCT "BRANCH_CD") FROM idm_branch_perf_v1)::float
  / NULLIF((SELECT COUNT(*) FROM branch), 0) AS perf_coverage,
  (SELECT COUNT(DISTINCT "BRANCH_CD") FROM idm_monthly_due_v2)::float
  / NULLIF((SELECT COUNT(*) FROM branch), 0) AS due_coverage,
  (SELECT COUNT(DISTINCT "BRANCH_CD") FROM idm_fee_stats_v3)::float
  / NULLIF((SELECT COUNT(*) FROM branch), 0) AS fee_coverage;
-- All should be ≥ 0.95 (95%+).

-- 3) Date range plausibility
SELECT MIN("MONTH_DT"), MAX("MONTH_DT"), COUNT(DISTINCT "MONTH_DT")
FROM idm_branch_perf_v1;
-- Should be the recent N months, no future dates, no gaps.

-- 4) Null density on monetary columns
SELECT
  COUNT("VAL_SUCCESS")::float / NULLIF(COUNT(*),0) AS val_success_density,
  COUNT("VAL_FAIL")::float / NULLIF(COUNT(*),0) AS val_fail_density,
  COUNT("TRN_AMT")::float / NULLIF(COUNT(*),0) AS trn_amt_density
FROM idm_branch_perf_v1
FULL OUTER JOIN idm_fee_stats_v3 USING ("BRANCH_CD","MONTH_DT");
-- Anything below 0.5 will produce unreliable answers under the
-- auto-injected time filter.

-- 5) BRANCH_CD type consistency
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE column_name = 'BRANCH_CD'
ORDER BY table_name;
-- All rows must show the same type. Mismatch breaks the join validator.
```

If any precondition fails, **fix the data first**. Do not build the
source on top of broken data and try to fix it through the semantic
layer. The semantic layer can't paper over PK violations or type
mismatches.
