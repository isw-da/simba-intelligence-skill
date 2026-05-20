# Debit-order payments processor

Use case for a company that processes debit-order collections on
behalf of lenders or merchants. The company runs collection attempts
against the customer's bank account on a schedule, charges fees on
each attempt, and reports performance to the underlying lender or
merchant ("branch" in the data model).

Built and field-tested against the the customer Branch Performance source
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
