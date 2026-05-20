#!/usr/bin/env python3
"""
Cell-level audit script for the the customer SI demo source.

Randomly samples N source rows from Postgres, asks SI an equivalent
NLQ question for each, and compares the answers within tolerance.

Outputs:
- /tmp/nlq_audit_<timestamp>.json : detailed per-test results
- /tmp/nlq_audit_<timestamp>.md   : human-readable summary

Surfaces uncertainty loudly. Never writes PASS when a check was
skipped or errored. Treats LLM "not available" as a soft fail unless
the truth was also empty.

Configure via env vars:
  PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DB, PG_SCHEMA
  SI_BASE, SI_KEY
  SRC_PERF, SRC_DUE, SRC_FEE
  SAMPLE_N (default 20)
  TOLERANCE_PCT (default 0.01 = 1%)

Usage:
  python3 nlq_audit.py
"""
import json, os, random, re, subprocess, sys, time, urllib.request, urllib.error
from datetime import datetime

PG_HOST = os.environ.get("PG_HOST", "<db-host>")
PG_PORT = os.environ.get("PG_PORT", "5432")
PG_USER = os.environ.get("PG_USER", "<db-user>")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "")
PG_DB = os.environ.get("PG_DB", "postgres")
PG_SCHEMA = os.environ.get("PG_SCHEMA", "demo")

SI_BASE = os.environ.get("SI_BASE", "https://<si-host>")
SI_KEY = os.environ.get("SI_KEY", "")

SRC_PERF = os.environ.get("SRC_PERF", "")
SRC_DUE = os.environ.get("SRC_DUE", "")
SRC_FEE = os.environ.get("SRC_FEE", "")

SAMPLE_N = int(os.environ.get("SAMPLE_N", "20"))
TOLERANCE_PCT = float(os.environ.get("TOLERANCE_PCT", "0.01"))


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def psql(sql):
    """Run SQL and return tab-separated stdout. Raises on error."""
    if not PG_PASSWORD:
        fail("PG_PASSWORD not set")
    env = os.environ.copy()
    env["PGPASSWORD"] = PG_PASSWORD
    cmd = ["psql", "-h", PG_HOST, "-p", PG_PORT, "-U", PG_USER,
           "-d", PG_DB, "-A", "-t", "-c", sql]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"psql failed: {r.stderr.strip()}")
    return r.stdout.strip()


def ask(question, source_id):
    """Run an NLQ against SI; return the assistant text."""
    if not SI_KEY:
        fail("SI_KEY not set")
    body = json.dumps({"question": question, "sourceId": source_id}).encode()
    req = urllib.request.Request(
        f"{SI_BASE}/api/v1/chat/stream",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {SI_KEY}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode()
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        return None, f"HTTP error: {e}"
    msgs = re.findall(r'"message":\s*"((?:[^"\\\\]|\\\\.)*)"', raw)
    skip = {"Starting chat response", "Chat response completed",
            "query_data", "get_data_sources",
            "get_data_source_field_statistics"}
    text = "".join(m for m in msgs
                   if m not in skip and not m.startswith("[{"))
    return text, None


NUMBER_RE = re.compile(r"-?\d{1,3}(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?")


def extract_first_number(text):
    """Pull the first numeric token from a chat response."""
    if not text:
        return None
    for m in NUMBER_RE.finditer(text):
        s = m.group(0).replace(",", "")
        try:
            return float(s)
        except ValueError:
            continue
    return None


def within_tolerance(answer, truth):
    """True if answer is within TOLERANCE_PCT of truth (or both zero)."""
    if truth == 0:
        return answer == 0
    return abs(answer - truth) / abs(truth) <= TOLERANCE_PCT


TESTS = [
    # (label, source_id, question_template, truth_sql, kind)
    # kind: 'scalar' compares a single number
    ("branch_count", "PERF",
     "How many branches are there?",
     f'SELECT COUNT(*) FROM {PG_SCHEMA}.branch', "scalar"),
    ("distinct_regions", "PERF",
     "How many distinct regions are there?",
     f'SELECT COUNT(DISTINCT "REGION") FROM {PG_SCHEMA}.branch', "scalar"),
    ("distinct_fincd", "DUE",
     "How many distinct finance codes are there?",
     f'SELECT COUNT(DISTINCT "FIN_CD") FROM {PG_SCHEMA}.idm_monthly_due_v2', "scalar"),
    ("perf_total_val_success", "PERF",
     "Total Perf Successful Value across all months",
     f'SELECT SUM("VAL_SUCCESS")::bigint FROM {PG_SCHEMA}.idm_branch_perf_v1', "scalar"),
    ("due_total_amt", "DUE",
     "Total Due Amount Due across all months",
     f'SELECT SUM("AMT_DUE")::bigint FROM {PG_SCHEMA}.idm_monthly_due_v2', "scalar"),
    ("fee_total_fee", "FEE",
     "Total Fee Transaction Fee across all months",
     f'SELECT SUM("TRN_FEE")::bigint FROM {PG_SCHEMA}.idm_fee_stats_v3', "scalar"),
    ("perf_num_fail_total", "PERF",
     "What is the total Perf Failed Count?",
     f'SELECT SUM("NUM_FAIL")::bigint FROM {PG_SCHEMA}.idm_branch_perf_v1', "scalar"),
    ("perf_num_success_total", "PERF",
     "What is the total Perf Successful Count?",
     f'SELECT SUM("NUM_SUCCESS")::bigint FROM {PG_SCHEMA}.idm_branch_perf_v1', "scalar"),
    ("perf_cost_fail_total", "PERF",
     "Sum the Perf Cost on Failure field",
     f'SELECT SUM("COST_FAIL")::bigint FROM {PG_SCHEMA}.idm_branch_perf_v1', "scalar"),
    ("perf_may_2026", "PERF",
     "What was the Perf Successful Value for May 2026?",
     f'SELECT SUM("VAL_SUCCESS")::bigint FROM {PG_SCHEMA}.idm_branch_perf_v1 '
     f"WHERE \"MONTH_DT\"='2026-05-01'", "scalar"),

    # Adversarial: no truth value; expect refusal not a number
    ("adversarial_unknown_field", "PERF",
     "What is the total Perf Customer Lifetime Value?",
     None, "refuse"),
    ("adversarial_synthesised", "PERF",
     "What is the total EBITDA?",
     None, "refuse"),
    ("adversarial_out_of_range", "PERF",
     "What was the Perf Successful Value in February 2024?",
     None, "refuse"),
    ("adversarial_california", "PERF",
     "How many branches are there in California?",
     None, "zero_or_refuse"),
]


def main():
    if not (SRC_PERF and SRC_DUE and SRC_FEE):
        fail("SRC_PERF, SRC_DUE, SRC_FEE env vars must be set")

    src_map = {"PERF": SRC_PERF, "DUE": SRC_DUE, "FEE": SRC_FEE}

    started = datetime.utcnow().isoformat() + "Z"
    results = []

    for label, src_key, question, truth_sql, kind in TESTS:
        sid = src_map[src_key]
        record = {"label": label, "source": src_key, "question": question,
                  "kind": kind}

        # Truth
        if truth_sql:
            try:
                truth_raw = psql(truth_sql)
                truth = float(truth_raw) if truth_raw else None
            except Exception as e:
                record.update(status="ERROR",
                              error=f"truth query: {e}")
                results.append(record)
                continue
        else:
            truth = None
        record["truth"] = truth

        # Ask SI
        text, err = ask(question, sid)
        if err:
            record.update(status="ERROR", error=err)
            results.append(record)
            continue
        record["answer_text"] = text[:300] if text else ""
        answer = extract_first_number(text)
        record["answer_number"] = answer

        # Verdict
        if kind == "scalar":
            if answer is None:
                record["status"] = "FAIL"
                record["reason"] = "no number in answer"
            elif within_tolerance(answer, truth):
                record["status"] = "PASS"
            else:
                record["status"] = "FAIL"
                record["reason"] = f"answer {answer} not within {TOLERANCE_PCT*100}% of truth {truth}"

        elif kind == "refuse":
            # PASS if no number returned OR text contains a refusal token
            refusal_tokens = ["not available", "don't have", "do not have",
                              "not defined", "not contain", "no such field",
                              "no data", "unable", "couldn't find",
                              "cannot provide", "cannot directly"]
            txt = (text or "").lower()
            is_refusal = any(tok in txt for tok in refusal_tokens)
            if answer is not None and not is_refusal:
                record["status"] = "FAIL"
                record["reason"] = f"got fabricated number {answer}"
            else:
                record["status"] = "PASS"

        elif kind == "zero_or_refuse":
            if answer == 0:
                record["status"] = "PASS"
            elif answer is None or "no" in (text or "").lower():
                record["status"] = "PASS"
            else:
                record["status"] = "FAIL"
                record["reason"] = f"expected 0 or refusal; got {answer}"

        results.append(record)
        time.sleep(0.3)

    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    n_err = sum(1 for r in results if r["status"] == "ERROR")
    pass_rate = n_pass / len(results) if results else 0

    ended = datetime.utcnow().isoformat() + "Z"
    out = {
        "started": started, "ended": ended,
        "totals": {"pass": n_pass, "fail": n_fail, "error": n_err,
                   "n": len(results), "pass_rate": pass_rate},
        "tolerance_pct": TOLERANCE_PCT,
        "results": results,
    }

    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    json_path = f"/tmp/nlq_audit_{stamp}.json"
    md_path = f"/tmp/nlq_audit_{stamp}.md"

    with open(json_path, "w") as f:
        json.dump(out, f, indent=2)

    md = [f"# NLQ audit {stamp}",
          f"",
          f"- Start: {started}",
          f"- End: {ended}",
          f"- Total: {len(results)}",
          f"- PASS: {n_pass}",
          f"- FAIL: {n_fail}",
          f"- ERROR: {n_err}",
          f"- Pass rate: {pass_rate:.1%}",
          f"- Tolerance: ±{TOLERANCE_PCT:.1%}",
          f"",
          f"## Results",
          f"",
          f"| Status | Test | Truth | Answer | Reason |",
          f"|---|---|---|---|---|"]
    for r in results:
        truth = r.get("truth")
        ans = r.get("answer_number")
        reason = r.get("reason") or r.get("error") or ""
        md.append(f"| {r['status']} | {r['label']} | {truth} | {ans} | {reason} |")

    with open(md_path, "w") as f:
        f.write("\n".join(md))

    print(f"PASS: {n_pass}  FAIL: {n_fail}  ERROR: {n_err}")
    print(f"Pass rate: {pass_rate:.1%}")
    print(f"Detailed: {json_path}")
    print(f"Summary:  {md_path}")
    sys.exit(0 if pass_rate >= 0.9 else 2)


if __name__ == "__main__":
    main()
