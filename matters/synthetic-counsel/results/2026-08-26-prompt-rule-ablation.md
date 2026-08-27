# Runs 3-4: fee-category prompt rule (with an instructive overshoot)

Date: 2026-08-26. Same corpus, model, settings, 40 questions. Change under
test: grounding rule 7 in prompt.txt (government fee != firm fee). Dense
retrieval code shipped but INACTIVE in these runs (no embedding model loaded),
so these runs isolate the prompt rule.

## Run 3: rule v1 -> fixed Q12, but OVERSHOT

Rule v1 stated only the negative (a government fee is not a firm fee).
- Q12 FIXED: "Not specified in the sources. The sources only mention the
  USPTO government fee ($130)..." - exactly the prescribed behavior.
- REGRESSION Q36: refused a GENUINE firm charge ("runs about fifteen hundred
  dollars", retrieved at #1, bm25 25.8) - the phrasing "runs about" no longer
  read as a firm fee to the newly suspicious model.
- REGRESSION Q9: kept fee categories, dropped all four amounts.
- Lesson: a one-sided semantic rule trades false positives for false
  negatives. Prompt rules need the positive case stated too.

## Run 4: rule v2 (adds "an amount a firm states for its own services IS its
fee, whatever the phrasing") -> both regressions resolved, Q12 stays fixed.

## Score progression (all runs, same 40 questions, same model)

| Run | Protocol / change | Correct | Wrong answers | Fabrications |
|---|---|---|---|---|
| 1 | mega-prompt (1 retrieval) | 18/40 (45%) | 0 | 0 |
| 2 | batch, per-question retrieval | 33/40 (82.5%) | 1 (Q12) | 0 |
| 2b | + stemming + scope-aware gate | 35/40 (87.5%) | 1 (Q12) | 0 |
| 4 | + fee-category rule v2 | **36/40 (90%)** | **0** | 0 |

## Probe highlight (run between 3 and 4)

Q36 once produced the full defense stack in one answer: verbatim quote
("fifteen hundred dollars"), an [INFERENCE] label on its own interpretation,
and UNVERIFIED NUMBER: 1,500 fired by the checker when the model also wrote
the numeral - which appears nowhere in the sources. Three layers, all correct.

## Remaining failures (4), all in known classes

- Q15, Q35: zero-overlap paraphrase -> dense retrieval (code shipped, awaits
  an embedding model in LM Studio).
- Q16: status question under --only scoping -> usage rule (run unscoped).
- Q18: partial - Bravo's amount chunk loses the top-5 race cross-corpus.
