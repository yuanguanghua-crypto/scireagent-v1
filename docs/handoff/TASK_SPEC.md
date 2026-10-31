# TASK SPEC — Protocol↔Method Link Audit

You are auditing a curated knowledge base of laboratory protocols. Each protocol record
is linked to a canonical *method* (a technique category). Your job is to judge whether
each link is genuinely correct, and to review the quality of written method summaries.

Read this file completely before producing any output. Two tasks, two input files.

---

## Inputs you receive

| File | Rows | Purpose |
|---|---|---|
| `CRITERIA.json` | 20 methods + 5 universal rules | **Authoritative** judgement rules |
| `METHOD_DEFS.json` | 83 entries, keyed by `method_id` | Method name + definition (see below) |
| `input_task_a.jsonl` | 14,975 | One row per protocol↔method link (Task A) |
| `input_task_b.jsonl` | 166 | One row per method field to review (Task B) |
| `gold_set.jsonl` | 56 | Calibration set with known answers — run this FIRST |
| `OUTPUT_SCHEMA.json` | — | Exact output shape |
| `RUBRIC.md` | — | Review criteria for Task B only |

Every input row carries everything except the method's own name/definition — those are
stored **once** in `METHOD_DEFS.json` (keyed by `method_id`) instead of being repeated in
all ~180 rows that reference the same method. This keeps each shard under the context limit.

### Resolving the method for a row

For every row, look up `METHOD_DEFS.json[str(method_id)]`:

```json
{"123": {"name": "PCR", "definition": "PCR amplifies specific DNA sequences...", "is_step_tag": false}}
```

- `name` and `definition` are the method context you need for judging.
- `is_step_tag` is background only — it does **not** change the verdict rules.
- If a `method_id` is missing from `METHOD_DEFS.json`, that is a data error: report it,
  do not guess.

---

## Task A — Is this link correct?

For each row of `input_task_a.jsonl`, decide one verdict:

- `on_topic` — the protocol's **core technique IS** this method.
- `tangential` — the method genuinely appears, but only as a non-core step.
- `wrong` — the protocol does not involve this method, or hits an exclusion clause.

### Decision procedure (follow in order)

1. Read the row's `criteria_key`.
2. If it is **not** `"general"`: read `CRITERIA.json` → `methods[criteria_key]`. Check the
   protocol against `essence`, then `must`, then `exclude`.
3. If it is `"general"`: apply only `universal_rules` plus the row's `method_definition`.
4. Stage 1 of `CRITERIA.json` `_how_to_use.precedence` applies: **the criteria override
   your own intuition.** If a protocol matches any `exclude` clause, the verdict is `wrong`
   — unless the method is still the protocol's core deliverable.

### Hard rules

1. **Criteria beat intuition.** You may not override an exclusion clause because you
   personally consider the protocol "basically related". If you do, the row is a format
   violation.
2. **Cite the clause you used.** `criteria_hit` must reference something concrete:
   `"exclude#2"`, `"must#1"`, `"universal#3"`, or `"definition"` when judging from
   `method_definition` alone. An empty `criteria_hit` is a format violation.
3. **Do not use `tangential` as a hedge.** It is only for protocols that genuinely contain
   the method as a real but non-core step. Empirical note from our own runs: `tangential`
   is the single largest source of disagreement (47 of 144 rows on one method), because it
   gets used as "I'm not sure". If unsure, decide `wrong` and set `confidence: "low"`.
4. **Judge the technique, not the words.** A protocol titled *"Isolation of DNA from mouse
   tail"* is `on_topic` for *Genomic DNA Extraction* even though it never uses that phrase.
   Conversely, a protocol about culturing kidney cells is **not** `on_topic` for
   *Pluripotent Stem Cell Culture* merely because both involve cells.
5. **Never infer from the link itself.** `link_source` and `link_status` are metadata we
   give you for context only. Do not treat an existing link as evidence that it is correct.

### Method already marked as a "common step"

Some rows carry `method_is_step_tag: true`. These four methods (Sanger Sequencing,
Enzymatic Labeling, Random Primer Method, End Labeling) are techniques that appear inside
other methods rather than standing alone. **This does not change your verdict rules** — it
is context explaining why these methods exist at all. Judge the same way.

---

## Task B — Is this written summary acceptable?

For each row of `input_task_b.jsonl`, review the `lines` array against `RUBRIC.md` and
return per-line findings. You are **not** rewriting the text. You are answering: does each
line pass, and if not, which rule does it break?

Output one record per (method_id, field) with a `findings` array, one entry per line.

---

## Calibration requirement (do this before the real run)

1. Run your pipeline on `gold_set.jsonl` first. Its rows have the same shape as Task A plus
   `expected_verdict` and `tier`.
2. Report: overall accuracy, accuracy split by `tier` (`human` / `consensus`), and the
   confusion matrix.
3. **If accuracy < 85%, stop and report it.** Do not proceed to the full 14,975 rows — a
   model that cannot reproduce the calibration set will not be trusted on the rest.
4. Send us the calibration report before the full run so we can approve.

---

## Output

- One JSON object per line (JSONL), UTF-8, no BOM.
- Field names and types exactly as in `OUTPUT_SCHEMA.json`. Extra fields are ignored;
  missing required fields reject the row.
- Keep input order. Do not deduplicate, filter, or re-sort.

## What NOT to do

- Do not invent protocol-level facts (yields, limits, times) that are not in the input row.
- Do not merge or split rows.
- Do not "fix" obvious upstream errors by reassigning a protocol to a different method.
  If a link is wrong, just say `wrong` — reassignment is a separate task.
- Do not output anything except JSONL for the data, and plain text for the reports.
