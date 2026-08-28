# Debit-order payments processor

> **Not runnable, and not yet demo-safe. Read this before showing anything.**
>
> Assessed 2026-08-28. Two things to know before this folder goes near a
> customer.
>
> 1. **It ships no data.** There is no CSV, no SQL seed, no fixture and no
>    generator anywhere in this repository. `sql-templates.py` and
>    `apply-rules.py` are API clients: they post source and rule definitions
>    to an SI tenant that must already contain tables named `branch`,
>    `branch_legal_entity`, `idm_branch_perf_v1`, `idm_monthly_due_v2` and
>    `idm_fee_stats_v3`. Without the original extract, `python3
>    sql-templates.py build` has nothing to build against. Everything here is
>    a description of a demo, not the demo. Building the synthetic equivalent
>    from `data-shape.md` is the missing piece.
> 2. **A real financial institution is named in the expected answers.**
>    `CAPITEC_SO` and `CAPITEC_TPPP` appear in `demo-flow.md`,
>    `two-sources-walkthrough.md`, `field-dictionary.md` and
>    `sql-templates.py`, and `demo-flow.md` closes on "83% of your forward
>    exposure sits with one funder". Capitec is a live South African bank.
>    Do not put that slide in front of anyone until those values are
>    replaced.
>
> The anonymisation pass was also a blind string substitution and left broken
> output: `starter-guide.md` contains `FROM the customer.branch b`, which will
> not parse, and three rules in `rules.md` end "a different the customer
> source" and would be sent to an LLM verbatim.
>
> What this folder IS good for: discovery, modelling reference, and the
> "what to avoid on the demo" section of `demo-flow.md`, which is the most
> reusable page here and applies to any SI demo.


Use case for a company that processes debit-order collections on
behalf of lenders or merchants. The company runs collection attempts
against the customer's bank account on a schedule, charges fees on
each attempt, and reports performance to the underlying lender or
merchant ("branch" in the data model).

Built and field-tested against the customer's Branch Performance source
(May 2026). Should fit any business with the same operating model:
debit-order origination, collection attempt, success/failure/dispute
tracking, fee revenue per attempt.

## Files in this folder

| File | Purpose |
|---|---|
| `README.md` | This file. Use case overview, demo flow, briefing notes |
| `data-shape.md` | Required tables, columns, cardinality, join keys |
| `question-bank.md` | 60+ NLQs organised by intent. Use as audit suite or demo deck |
| `rules.md` | Rules Management content to apply pre-demo |
| `field-metadata.md` | Per-field metadata template |
| `derived-fields.md` | Precomputed ratios to add as Postgres generated columns |
| `demo-flow.md` | A scripted 10-question demo path tested for accuracy |

## Who this fits

Payments processors with the following operating model:

- They originate or service debit-order collections for third parties.
- Each "branch" or "merchant" or "client" is a customer of the
  processor.
- Each branch has monthly performance metrics: count of successful
  collections, count of failed, dispute counts, fee revenue per
  category.
- The processor charges fees per collection attempt and per dispute.
- The processor has internal costs per collection attempt.
- There's a separate dim for legal entity / regulatory info per
  branch.

Examples: the customer (South Africa), DebiCheck operators, US ACH
processors handling pre-authorised debits, UK Direct Debit bureaux.

## Who this does NOT fit

- B2C payments (Stripe, Square, Adyen) — different schema entirely
- Real-time payment rails — no monthly aggregation
- Card-acquirer reporting — different metric vocabulary
- Lender-side analytics — the customer is the lender, not the processor

## What the LLM gets right (out of the box)

When the template is applied correctly:

- Total collections, success rate, failure rate by branch, region,
  industry
- Monthly trends in collection value
- Top/bottom rankings by any monetary metric
- Single-month value lookups (with "for X" phrasing, not "in X")
- Adversarial questions (refuses unknown fields, out-of-range dates)

## What's hard regardless

These are LLM behaviour issues we can mitigate but not eliminate:

- Synthesis of derived metrics that aren't in the data
  (Customer Acquisition Cost, EBITDA, Net Profit Margin, Churn).
  **Mitigation: define ratios as derived fields. See
  `derived-fields.md`.**
- Phrasing sensitivity: same question asked two ways can give two
  answers. **Mitigation: pre-verify each demo question 3 times.**
- Bare wording leaks to other sources in multi-source tenants.
  **Mitigation: single-source tenant for the customer, OR prefix
  every fact-table label with a source-unique tag.**

## Briefing the audience

Before any demo, tell the prospect three things:

1. "Lead each question with the source word."
   In our case: "Perf", "Due", "Fee". This avoids the cross-source
   leak you'd otherwise hit.

2. "If a number looks wrong, click the `{ }` icon next to the answer."
   That shows the raw SQL response. If it's `[]`, the prose answer is
   fabricated. This is the single most important habit for prospects
   using the tool unsupervised.

3. "Ask for fields that exist, not derived metrics by name."
   "Failure rate" works because we precomputed it. "EBITDA" doesn't
   because we didn't. The tool tells you when a metric is missing.
