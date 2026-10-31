# ACCEPTANCE — how we decide whether to trust the returned results

Five gates. Each has a numeric threshold and a defined action when it fails. A run that
fails gate 1 or 2 is **not used at all**; gate 3–5 failures are handled per-record.

---

## Gate 1 — Format compliance  (must be 100%)

Run `python validate_output.py --input <out.jsonl>`. It checks:

- every line parses as JSON
- required fields present, enum values legal
- `criteria_hit` non-empty and matches the allowed pattern
- Task B returns exactly one finding per input line, `line_index` in range
- no duplicate `(method_id, protocol_id)` pairs in Task A
- row count equals the input row count

**Pass:** 0 invalid lines, 0 missing rows, 0 duplicates.
**Fail:** the whole batch is returned for re-run. Do not hand-fix individual lines.

---

## Gate 2 — Calibration accuracy  (must be ≥ 85%)

Run on `gold_set.jsonl` before the full set.

| Tier | Rows | Required |
|---|---|---|
| `human` (verified against source text) | 16 | ≥ 85% |
| `consensus` (two prior models agreed) | 40 | ≥ 85% |
| Overall | 56 | ≥ 85% |

**Additional requirement:** accuracy on the `human` tier must not be more than 10 points
below the `consensus` tier. Consensus rows are easier (both prior models agreed), so a large
gap means the model is fitting easy cases and failing on the genuinely hard ones.

**Fail:** the model is not used. Report which tier failed and the confusion matrix.

---

## Gate 3 — Disagreement structure  (analysed, not thresholded)

After the full run we cross-tabulate three independent judgements: our two prior models
(`flash`, `pro`) and yours.

| Pattern | Meaning | Action |
|---|---|---|
| 3-way agreement | high confidence | accept automatically |
| 2-of-3 majority, the odd one out is `tangential` | known ambiguity zone | accept majority, flag row |
| 2-of-3 majority, the odd one is `wrong` vs `on_topic` | substantive conflict | **escalate to human** |
| 3-way disagreement | definition is broken | escalate; do not average |

We do **not** require a specific agreement rate — you are the third opinion, not a truth
source. What matters is that disagreements are structured and tractable.

---

## Gate 4 — Human spot-check  (must be ≥ 80%)

We draw a random 5% of your Task A output (≈ 750 rows), stratified across methods and across
`confidence` levels, and read the protocol text ourselves.

**Pass:** ≥ 80% of sampled rows agree with your verdict.
**Fail:** the batch is suspect — we re-sample another 5%; if still < 80%, the whole batch is
returned.

Report the spot-check result to us before we act on the data.

---

## Gate 5 — Downstream safety  (per-record, before any deletion)

Before any link is hidden or deleted based on your verdict, each row must clear two checks:

1. **Not the protocol's only link.** 3,807 protocols currently have exactly one link and it
   is judged `wrong`. Removing it would orphan the protocol. Those go to a separate
   re-assignment queue, never straight to deletion.
2. **Confidence is not `low`.** `low` rows go to human review regardless of verdict.

We also require, per batch:

- an exact backup of the rows to be changed (JSON dump, row count matched)
- `--dry-run` output reviewed and approved by a human before `--apply`
- a rollback command documented

---

## Report format we expect back

Plain text or Markdown, containing:

1. Gate 1 result — invalid lines, missing rows, duplicates (with sample errors)
2. Gate 2 result — accuracy overall and per tier, plus the confusion matrix
3. Verdict distribution — counts for `on_topic` / `tangential` / `wrong`
4. `confidence` distribution — how many `low` (these come back to us for human review)
5. Gate 3 analysis is ours to run, but tell us if you noticed systematic patterns
6. Any rows you refused to judge, and why

---

## What happens after acceptance

| Verdict | Action on our side |
|---|---|
| `wrong` + `high` confidence + 3-way agreement | mark link `status='review'` (hidden from public read paths), reversible |
| `wrong` but 2-of-3 or `medium` | queue for human仲裁 |
| `tangential` | keep visible, demote display order |
| `on_topic` | keep |
| `low` confidence (any verdict) | human review, no automated action |

Nothing is deleted until a human has approved the dry-run. Every change is backed up and
reversible for 30 days.
