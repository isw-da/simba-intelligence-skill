#!/usr/bin/env python3
"""
SQL templates and source builder for the debit-order-payments
Custom SQL Entity pattern.

Usage to build the source in a new tenant:
  python3 sql-templates.py build \
    --base https://<tenant>/<si-mount> \
    --key  <api-key> \
    --connection <connection-id> \
    --schema <schema-name>

Compute cost:
- POST source: one connection probe per entity. Negligible.
- Each Custom SQL entity registered: zero compute until queried.
- Each NLQ: one query per turn. Use the all-time entity for totals
  (single GROUP BY against your fact table) and the monthly entity
  for trends.

For a Fabric backend, the all-time aggregates are cheap (single
scan + GROUP BY by branch_cd). The monthly entity SELECTs without
aggregation, so per-row cost is whatever your fact table is.

If compute is a concern, set rawCacheEnabled=true on the all-time
entities (15-minute cache by default). See cacheSettings below.
"""
import argparse, json, sys, urllib.request, urllib.error

# ----- Per-entity SQL templates (parametrised by schema) -----

LEGAL_SQL = """SELECT DISTINCT ON ("BRANCH_CD"::text)
  "BRANCH_CD"::text AS branch_cd,
  "INDUSTRY","LEGAL_STRUCTURE","REG_ENTITY","TRADE_NAME"
FROM {schema}.branch_legal_entity"""

PERF_MONTHLY_SQL = """SELECT
  b."BRANCH_CD"::text AS branch_cd,
  p."MONTH_DT" AS month_dt,
  COALESCE(p."NUM_SUCCESS",0) AS num_success,
  COALESCE(p."NUM_FAIL",0) AS num_fail,
  COALESCE(p."VAL_SUCCESS",0) AS val_success,
  COALESCE(p."VAL_FAIL",0) AS val_fail,
  COALESCE(p."COST_SUCCESS",0) AS cost_success,
  COALESCE(p."COST_FAIL",0) AS cost_fail,
  COALESCE(p."FEE_SUCCESS",0) AS fee_success,
  COALESCE(p."FEE_FAIL",0) AS fee_fail,
  (COALESCE(p."VAL_SUCCESS",0) - COALESCE(p."VAL_FAIL",0)) AS net_collection_value,
  (COALESCE(p."FEE_SUCCESS",0)+COALESCE(p."FEE_FAIL",0)
   - COALESCE(p."COST_SUCCESS",0)-COALESCE(p."COST_FAIL",0)) AS net_revenue_from_fees
FROM {schema}.branch b
LEFT JOIN {schema}.idm_branch_perf_v1 p ON p."BRANCH_CD"::text = b."BRANCH_CD"
WHERE p."MONTH_DT" IS NOT NULL"""

PERF_ALLTIME_SQL = """SELECT
  b."BRANCH_CD"::text AS branch_cd,
  SUM(COALESCE(p."NUM_SUCCESS",0)) AS total_num_success,
  SUM(COALESCE(p."NUM_FAIL",0)) AS total_num_fail,
  SUM(COALESCE(p."VAL_SUCCESS",0)) AS total_val_success,
  SUM(COALESCE(p."VAL_FAIL",0)) AS total_val_fail,
  SUM(COALESCE(p."COST_SUCCESS",0)) AS total_cost_success,
  SUM(COALESCE(p."COST_FAIL",0)) AS total_cost_fail,
  SUM(COALESCE(p."FEE_SUCCESS",0)) AS total_fee_success,
  SUM(COALESCE(p."FEE_FAIL",0)) AS total_fee_fail,
  SUM(COALESCE(p."VAL_SUCCESS",0)-COALESCE(p."VAL_FAIL",0)) AS total_net_collection_value,
  SUM(COALESCE(p."FEE_SUCCESS",0)+COALESCE(p."FEE_FAIL",0)
     -COALESCE(p."COST_SUCCESS",0)-COALESCE(p."COST_FAIL",0)) AS total_net_revenue_from_fees
FROM {schema}.branch b
LEFT JOIN {schema}.idm_branch_perf_v1 p ON p."BRANCH_CD"::text = b."BRANCH_CD"
GROUP BY b."BRANCH_CD" """

DUE_MONTHLY_SQL = """SELECT
  b."BRANCH_CD"::text AS branch_cd,
  d."MONTH_DT" AS month_dt,
  d."FIN_CD" AS fin_cd,
  COALESCE(d."NUM_DUE",0) AS num_due,
  COALESCE(d."AMT_DUE",0) AS amt_due
FROM {schema}.branch b
LEFT JOIN {schema}.idm_monthly_due_v2 d ON d."BRANCH_CD"::text = b."BRANCH_CD"
WHERE d."MONTH_DT" IS NOT NULL"""

DUE_ALLTIME_SQL = """SELECT
  b."BRANCH_CD"::text AS branch_cd,
  SUM(COALESCE(d."NUM_DUE",0)) AS total_num_due,
  SUM(COALESCE(d."AMT_DUE",0)) AS total_amt_due
FROM {schema}.branch b
LEFT JOIN {schema}.idm_monthly_due_v2 d ON d."BRANCH_CD"::text = b."BRANCH_CD"
GROUP BY b."BRANCH_CD" """

FEE_MONTHLY_SQL = """SELECT
  b."BRANCH_CD"::text AS branch_cd,
  f."MONTH_DT" AS month_dt,
  f."PMT_STREAM" AS pmt_stream,
  COALESCE(f."TRN_COUNT",0) AS trn_count,
  COALESCE(f."TRN_AMT",0) AS trn_amt,
  COALESCE(f."TRN_FEE",0) AS trn_fee
FROM {schema}.branch b
LEFT JOIN {schema}.idm_fee_stats_v3 f ON f."BRANCH_CD"::text = b."BRANCH_CD"
WHERE f."MONTH_DT" IS NOT NULL"""

FEE_ALLTIME_SQL = """SELECT
  b."BRANCH_CD"::text AS branch_cd,
  SUM(COALESCE(f."TRN_COUNT",0)) AS total_trn_count,
  SUM(COALESCE(f."TRN_AMT",0)) AS total_trn_amt,
  SUM(COALESCE(f."TRN_FEE",0)) AS total_trn_fee
FROM {schema}.branch b
LEFT JOIN {schema}.idm_fee_stats_v3 f ON f."BRANCH_CD"::text = b."BRANCH_CD"
GROUP BY b."BRANCH_CD" """


# ----- Field labels (applied after entity discovery) -----

LABELS = {
    "branch_cd": "Branch Code",
    "region": "Region",
    "status": "Branch Status",
    "description": "Branch Name",
    "industry": "Industry",
    "legal_structure": "Legal Structure",
    "reg_entity": "Legal Entity Name",
    "trade_name": "Trading Name",
    "month_dt": "Month",
    "fin_cd": "Finance Code",
    "pmt_stream": "Payment Stream",
    # Per-month perf fact
    "num_success": "Perf Successful Count",
    "num_fail": "Perf Failed Count",
    "val_success": "Perf Successful Value",
    "val_fail": "Perf Failed Value",
    "cost_success": "Perf Cost on Success",
    "cost_fail": "Perf Cost on Failure",
    "fee_success": "Perf Fees on Success",
    "fee_fail": "Perf Fees on Failure",
    "net_collection_value": "Perf Net Collection Value",
    "net_revenue_from_fees": "Perf Net Revenue from Fees",
    # All-time perf
    "total_num_success": "All-Time Perf Successful Count",
    "total_num_fail": "All-Time Perf Failed Count",
    "total_val_success": "All-Time Perf Successful Value",
    "total_val_fail": "All-Time Perf Failed Value",
    "total_cost_success": "All-Time Perf Cost on Success",
    "total_cost_fail": "All-Time Perf Cost on Failure",
    "total_fee_success": "All-Time Perf Fees on Success",
    "total_fee_fail": "All-Time Perf Fees on Failure",
    "total_net_collection_value": "All-Time Perf Net Collection Value",
    "total_net_revenue_from_fees": "All-Time Perf Net Revenue from Fees",
    # Due
    "num_due": "Due Count Due",
    "amt_due": "Due Amount Due",
    "total_num_due": "All-Time Due Count Due",
    "total_amt_due": "All-Time Due Amount Due",
    # Fee
    "trn_count": "Fee Transaction Count",
    "trn_amt": "Fee Transaction Amount",
    "trn_fee": "Fee Transaction Fee",
    "total_trn_count": "All-Time Fee Transaction Count",
    "total_trn_amt": "All-Time Fee Transaction Amount",
    "total_trn_fee": "All-Time Fee Transaction Fee",
}

META = {
    "val_success": "Monetary value of successful debit-order collections at this branch (per month)",
    "val_fail": "Monetary value of failed debit-order collections at this branch (per month)",
    "total_val_success": "Sum of all successful collection values across all months for this branch. Use this for all-time totals.",
    "total_val_fail": "Sum of all failed collection values across all months for this branch.",
    "total_net_collection_value": "All-time net collection value (successes minus failures).",
    "total_net_revenue_from_fees": "All-time net revenue from fees (fees minus costs).",
    "amt_due": "Monthly amount due to be collected from this branch",
    "total_amt_due": "All-time total amount due across all months for this branch",
    "trn_fee": "Monthly fee revenue collected on transactions at this branch",
    "total_trn_fee": "All-time total fee revenue at this branch",
    "region": "Geographic region of the branch",
    "industry": "Primary industry classification of the legal entity behind the branch",
    "month_dt": "Calendar month for the fact row",
    "fin_cd": "Finance / funder code (e.g. CAPITEC_SO, CAPITEC_TPPP)",
    "pmt_stream": "Payment stream type (EFT, EFTS, EFTD, ACOL, SEFT)",
}


# ----- API helpers -----

def req(base, key, method, path, body=None):
    CT = "application/vnd.composer.v3+json"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(base + path, data=data, method=method,
        headers={"Authorization": f"Bearer {key}",
                 "Accept": CT, "Content-Type": CT})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            txt = resp.read().decode()
            return resp.status, (json.loads(txt) if txt else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def build(base, key, conn, schema, name=None):
    """Build the full eight-entity Custom SQL source."""
    payload = {
        "name": name or "Debit-Order Operations (Custom SQL pattern)",
        "description": "Platform-only semantic model: dimension + dedup'd legal + per-month and all-time aggregates for perf, due, fee. All transformations in Custom SQL.",
        "storage": {
            "dataEntities": [
                {"id": "branch", "name": "Branches", "type": "SINGLE_COLLECTION",
                 "singleCollection": {"connectionId": conn, "schema": schema,
                                      "collection": "branch", "parameters": {}}},
                {"id": "legal", "name": "Legal Entities", "type": "CUSTOM_SQL",
                 "customSql": {"connectionId": conn, "sql": LEGAL_SQL.format(schema=schema)}},
                {"id": "perf_monthly", "name": "Branch Performance Monthly", "type": "CUSTOM_SQL",
                 "customSql": {"connectionId": conn, "sql": PERF_MONTHLY_SQL.format(schema=schema)}},
                {"id": "perf_alltime", "name": "Branch Performance All-Time", "type": "CUSTOM_SQL",
                 "customSql": {"connectionId": conn, "sql": PERF_ALLTIME_SQL.format(schema=schema)}},
                {"id": "due_monthly", "name": "Monthly Dues Monthly", "type": "CUSTOM_SQL",
                 "customSql": {"connectionId": conn, "sql": DUE_MONTHLY_SQL.format(schema=schema)}},
                {"id": "due_alltime", "name": "Monthly Dues All-Time", "type": "CUSTOM_SQL",
                 "customSql": {"connectionId": conn, "sql": DUE_ALLTIME_SQL.format(schema=schema)}},
                {"id": "fee_monthly", "name": "Fee Statistics Monthly", "type": "CUSTOM_SQL",
                 "customSql": {"connectionId": conn, "sql": FEE_MONTHLY_SQL.format(schema=schema)}},
                {"id": "fee_alltime", "name": "Fee Statistics All-Time", "type": "CUSTOM_SQL",
                 "customSql": {"connectionId": conn, "sql": FEE_ALLTIME_SQL.format(schema=schema)}},
            ],
            "joins": []
        }
    }
    code, body = req(base, key, "POST", "/discovery/api/sources", payload)
    if code != 200:
        print(f"POST failed: {code} {body}", file=sys.stderr)
        sys.exit(1)
    sid = body["id"]
    print(f"Source created: {sid}", file=sys.stderr)

    # Discover branch_cd field names per entity (they may be suffixed)
    def find_bcd(eid):
        for e in body["storage"]["dataEntities"]:
            if e["id"] != eid: continue
            for f in e.get("nativeFields", []):
                n = f.get("name", "")
                if n == "branch_cd" or n.startswith("branch_cd"):
                    return f["fieldName"]
        return None

    # Build joins from branch hub to every other entity
    body["storage"]["joins"] = []
    for other in ["legal", "perf_monthly", "perf_alltime",
                  "due_monthly", "due_alltime",
                  "fee_monthly", "fee_alltime"]:
        rhs = find_bcd(other)
        if not rhs:
            print(f"WARN: no branch_cd in {other}", file=sys.stderr)
            continue
        body["storage"]["joins"].append({
            "type": "LEFT",
            "leftDataEntity": {"dataEntityId": "branch", "dimension": False},
            "rightDataEntity": {"dataEntityId": other, "dimension": False},
            "conditions": [{"leftFieldName": "branch_cd", "rightFieldName": rhs}]
        })

    # Apply labels + metadata
    for e in body["storage"]["dataEntities"]:
        for f in e.get("nativeFields", []):
            f.pop("description", None)
            if f.get("disabledCapabilities") == ["PLAYING"]:
                f["disabledCapabilities"] = []
            no = f.get("origin", {}).get("nativeOrigin", {})
            if "metaFlags" in no and no["metaFlags"] == []:
                no["metaFlags"] = ["PLAYABLE"]
            name = f.get("name", "")
            base_name = name.rsplit("_", 1)[0] if name[-1:].isdigit() else name
            if base_name in LABELS:
                f["label"] = LABELS[base_name]
            elif name in LABELS:
                f["label"] = LABELS[name]
            if name in META:
                f["fieldMetadata"] = {"description": META[name]}
            elif base_name in META:
                f["fieldMetadata"] = {"description": META[base_name]}

    code, body2 = req(base, key, "PUT", f"/discovery/api/sources/{sid}", body)
    if code != 200:
        print(f"PUT failed: {code} {body2}", file=sys.stderr)
        sys.exit(1)

    # Disable timebar
    gs = req(base, key, "GET", f"/discovery/api/sources/{sid}/global-settings")[1]
    if gs and "timebar" in gs:
        gs["timebar"]["enabled"] = False
        req(base, key, "PUT", f"/discovery/api/sources/{sid}/global-settings", gs)

    # Flush cache
    req(base, key, "DELETE", f"/discovery/api/sources/{sid}/cache")

    print(sid)


def export(base, key, sid, outfile):
    code, body = req(base, key, "GET", f"/discovery/api/sources/{sid}")
    if code != 200:
        print(f"GET failed: {code}", file=sys.stderr); sys.exit(1)
    # Strip mutable bits
    for k in ("id", "auditable", "projectId", "folderId"):
        body.pop(k, None)
    with open(outfile, "w") as f:
        json.dump(body, f, indent=2)
    print(f"Source exported to {outfile}", file=sys.stderr)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="Build a fresh source in a tenant")
    b.add_argument("--base", required=True)
    b.add_argument("--key", required=True)
    b.add_argument("--connection", required=True)
    b.add_argument("--schema", required=True)
    b.add_argument("--name")
    e = sub.add_parser("export", help="Export an existing source to JSON")
    e.add_argument("--base", required=True)
    e.add_argument("--key", required=True)
    e.add_argument("--sid", required=True)
    e.add_argument("--out", required=True)
    args = p.parse_args()
    if args.cmd == "build":
        build(args.base, args.key, args.connection, args.schema, args.name)
    elif args.cmd == "export":
        export(args.base, args.key, args.sid, args.out)
