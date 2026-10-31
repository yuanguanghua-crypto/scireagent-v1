# RUBRIC — Task B (advantages / limitations review)

You review each line independently. Do not rewrite unless the fix is mechanical. Cite rule
ids `R1`–`R7` in `rule_violations`. A line that breaks two rules lists both.

Every rule below was derived from a real failure we observed on this exact corpus, so the
examples are not hypothetical.

---

## R1 — Method-level, not variant-level  **(the most common failure)**

A line must remain true for **most runs of the method**, regardless of which specific
protocol a lab chooses. If a different lab ran this method with a different protocol and the
line would become false, it is variant-level → **fail**.

| | Example | Why |
|---|---|---|
| FAIL | "CTAB-chloroform chemistry is adaptable to 96-well format" | Names one extraction chemistry — a variant choice |
| FAIL | "Universal primer designs can exploit conserved regions" | One primer strategy, not PCR itself |
| FAIL | "SDS-based lysis buffers stabilise samples for archiving" | One buffer system |
| PASS | "Yields high-molecular-weight DNA suitable for long-read sequencing" | True of the method at large |
| PASS | "Requires only a thermal cycler and standard reagents" | Structural property of the method |

**Self-test you should apply:** *would this still be true if another lab ran the same method
with a different protocol?* If no → R1.

---

## R2 — No invented numbers

Any specific sensitivity, yield, detection limit, dynamic range, turnaround time or
comparison figure must come from the input row's `method_definition`. If a number appears
that is not there, fail. Qualitative claims ("sensitive", "high yield") without a figure are
acceptable.

- FAIL: "detects as few as 10 copies per reaction"
- FAIL: "recovers >90% of input DNA"
- PASS: "detects low-abundance targets"

---

## R3 — No vendor, brand, or catalogue references

- FAIL: "uses the Qubit assay", "NEBNext-compatible", "TaqMan probes", "Cat. #E2612"
- PASS: "uses a fluorescent dye–based quantification step"

Note: generic reagent classes are fine ("chloroform", "ethanol"); branded kits are not.

---

## R4 — No marketing language

Banned words: revolutionary, cutting-edge, state-of-the-art, powerful, breakthrough,
world-class, best-in-class, game-changing, unparalleled, superior, seamless, robust
(as a bare adjective without object).

- FAIL: "a powerful and versatile approach"
- PASS: "tolerates degraded input"

---

## R5 — Format: one claim per line

Each line states exactly one advantage or limitation. Combined claims must be split.

- FAIL: "Fast, cheap and highly specific" → three claims
- FAIL: "1. High specificity" → carries a list marker
- PASS: "Runs in a single working day"

Also fail if a line exceeds 25 words (it is then a paragraph, not an entry).

---

## R6 — An advantage must be a reason to *choose* the method

Not a description of what the method does. Test: could the sentence also appear in a neutral
definition? If yes, it is a description, not an advantage.

| | Example | Why |
|---|---|---|
| FAIL | "Amplifies a target region" | Description — that is just what PCR is |
| PASS | "Amplifies from very small amounts of starting material" | A reason to pick it |
| FAIL | "Uses cells" | Too generic to be a reason |
| PASS | "Uses standard incubator culture without specialised instrumentation" | Concrete advantage |

---

## R7 — A limitation must be a real constraint

Not a neutral fact, not a back-handed advantage, not a limitation of a *different* method.

| | Example | Why |
|---|---|---|
| FAIL | "Requires a laboratory" | Not a meaningful constraint |
| FAIL | "Results depend on the operator" | Too vague to be actionable — name the failure mode |
| PASS | "Contamination with trace template causes false positives; strict handling is needed" | Names the failure mode |
| PASS | "Amplicon length and fidelity are limited by polymerase processivity and error rate" | Names the mechanism |

---

## Output mapping

| Situation | `overall` |
|---|---|
| All lines pass | `accept` |
| 1 line fails, or ≥1 line has a mechanical fix (`suggested_rewrite` non-null) | `accept_with_edits` |
| More than half the lines fail | `reject` |

`line_index` is **0-based** and refers to the input row's `lines` array. You must return
exactly one finding per line — missing indices reject the record.

---

## Calibration note

Task B has no gold set. Instead, calibrate by running on **20 rows we already know are good**
(they came from our prompt-v3 run whose output we manually reviewed): if your pipeline
rejects more than 2 of those 20, your thresholds are too strict — report it before the full
run.
