# Demo flow

A 10-question scripted demo path that exercises the full surface and
has been pre-verified to return correct answers (≥ 3 successful runs
per question).

Each question is annotated with the source to select in the
Playground dropdown, the expected approximate answer, and a "next
step" tied to the demo narrative.

## Pre-demo checklist

- [ ] Three sources visible in tenant
- [ ] All rules from `rules.md` applied
- [ ] All `fieldMetadata` from `field-metadata.md` applied
- [ ] Source caches flushed via DELETE
- [ ] Each of these 10 questions dry-run 3 times in last 24 hours

If any question failed on dry-run, swap it for a Tier-1 question
from `question-bank.md`. Do not improvise.

---

## Q1 — Establish scale

**Source**: Branch Performance
**Question**: How many branches are there?
**Expected**: "There are 1000 branches."
**Narrative**: "So this is your full operating footprint. Every
collection attempt you process flows through one of these branches."

---

## Q2 — Show grouping works

**Source**: Branch Performance
**Question**: How many branches are there in each region?
**Expected**: 57-row table, Free State 88 top, etc.
**Narrative**: "Notice this returned every region — including the
ones with null values labelled as (unknown). That's a rule we set:
no silent dropping of dimension values. Auditors care about this."

---

## Q3 — The headline number

**Source**: Branch Performance
**Question**: Total Perf Successful Value across all months
**Expected**: "R<value>.00"
**Narrative**: "That's your gross successful collection value over
the trailing 12 months. Rand prefix because we set tenant-wide
currency rules — works for any operator running in their local
currency."

---

## Q4 — Top performers

**Source**: Branch Performance
**Question**: Top 5 regions by Perf Successful Value
**Expected**: Free State <value>; ECape 1,368,984,079; etc.
**Narrative**: "Free State carries half your collections. Worth a
conversation about why."

---

## Q5 — Time trend

**Source**: Branch Performance
**Question**: Perf Successful Value by month
**Expected**: 12-month series ending May 2026
**Narrative**: "September was the peak. What happened in September?
That's the next discovery question for our analyst team."

---

## Q6 — Compute a ratio (cross-source robustness)

**Source**: Branch Performance
**Question**: What is the success rate?
**Expected**: "0.8358" or "83.58%"
**Narrative**: "Eighty-three percent overall success. That's the
micro rate, weighted by volume — we set a rule that computes it
correctly rather than per-branch-averaging. The distinction matters
for fairness."

---

## Q7 — Show a precomputed business metric

**Source**: Branch Performance
**Question**: What is the total Perf Net Collection Value?
**Expected**: "9,516,802,098"
**Narrative**: "We pre-compute this in the data layer. The AI never
synthesises business metrics — only ones a data engineer has
defined. If you asked it for EBITDA, it would tell you that's not a
field, not invent one."

---

## Q8 — Defensive boundary (the "oh wow")

**Source**: Branch Performance
**Question**: What is the total Customer Acquisition Cost?
**Expected**: "I don't have that metric in this data source"
**Narrative**: "This is the difference between an analytics tool and
a chatbot. We won't make up an answer. If the field isn't defined,
you get told. Your business analysts can trust that what comes back
is what's in the data."

---

## Q9 — Across sources

**Source**: Monthly Dues
**Question**: Total Due Amount Due across all months
**Expected**: "R20,979,420,601"
**Narrative**: "Switch source. Now we're looking at forward
obligations rather than completed collections. Same UI, same rules,
different fact table."

---

## Q10 — The closer

**Source**: Monthly Dues
**Question**: Total Due Amount Due by finance code
**Expected**: CAPITEC_SO R17.4B; CAPITEC_TPPP R3.5B
**Narrative**: "Eighty-three percent of your forward exposure sits
with one funder. That's a concentration question for risk. We can
follow up by drilling into branches in that finance code."

---

## What to avoid on the demo

Do NOT ask:

- "What's the total amount?" (bare wording — leaks in multi-source
  tenants)
- "What's the EBITDA / churn rate / customer lifetime value?"
  (synthesis-prone)
- "What's the Perf Successful Value in May 2026?" (use "for May"
  instead of "in May")
- "Which industries have the most branches?" (returns partial
  industry list)

If a prospect asks one of these mid-demo:

- Bare wording → "Let me rephrase that: do you mean the total
  successful value or the total amount due?"
- Synthesised metric → "That's not a field we've defined; we can
  add it as a derived metric in five minutes if it's load-bearing
  for you."
- "In May" → restate as "for May" and continue.
- Partial industry → switch to "Top industries by Perf Successful
  Value" which works.

## Time

Allow 12-15 minutes for the 10 questions plus narrative. Don't rush
between questions; the silence while the chart loads is worth more
than the chart itself, because it reads as "real query happening in
real time".
