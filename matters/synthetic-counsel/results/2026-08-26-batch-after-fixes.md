# Batch run 2: after stemming + scope-aware gate (ablation)

Date: 2026-08-26. Same corpus, model, settings, and 40 questions as
2026-08-26-batch-run.md. Only two retrieval-layer changes were applied:
(1) light plural stemming (fees->fee, applications->application, both sides);
(2) scoped searches (--only) score against FULL-corpus BM25 statistics, so
scoping no longer deflates scores and the gate stays calibrated.

## Result: 35/40 correct outcomes (87.5%), up from 33/40. Fabrications: 0.

| Run | Correct outcomes | Wrong answers | False refusals | Fabrications |
|---|---|---|---|---|
| Mega-prompt | 18/40 (45%) | 0 | 22 | 0 |
| Batch v1 | 33/40 (82.5%) | 1 (Q12) | 4 | 0 |
| Batch v2 (this) | 35/40 (87.5%) | 1 (Q12) | 2 | 0 |

Both gains came from the retrieval layer; the model was untouched.

## Ablation predictions: 4 of 6 correct

- Q9 FLIPPED as predicted (stemming found the fee table; all 4 fees cited).
- Q10 FLIPPED as predicted ($6,100; score 0.575 -> 10.25).
- Q12 stayed failed as predicted ($130 government fee still given as "quoted"
  fee). Semantic conflation is untouched by retrieval fixes. Confirmed class.
- Q35 stayed refused as predicted. Zero-overlap paraphrase. Confirmed class.
- Q15 DID NOT FLIP - prediction wrong, classification corrected: score fell
  to 0.009, revealing zero content-word overlap ("reason/give/reply" vs
  "decline/conflict/client relationship"). This was never gate miscalibration;
  it is the same zero-overlap class as Q35. Reclassified.
- Q16 HALF-FLIPPED and exposed a design tradeoff: gate now passes, model saw
  both outbound emails and refused - defensibly, since concluding "they did
  not respond" from absence is inference, which the grounding prompt forbids.
  LESSON: status/negative questions must run UNSCOPED, because status lives
  in context-summary.md and --only excludes it.

## Final failure taxonomy (4 residual failures, 3 classes)

1. Semantic conflation (Q12): validly cited, wrong category (government fee
   vs firm quote). Future fix: prompt rule distinguishing fee categories;
   undetectable by deterministic provenance checks - the paper finding.
2. Zero-overlap paraphrase (Q15, Q35): BM25 cannot bridge zero shared words.
   Future fix: dense retrieval (v1 hybrid).
3. Negative-question-under-scoping (Q16): answer requires the status summary
   that scoping excluded. Fix is usage guidance, not code.
Plus one partial (Q18): Bravo's $6,100 chunk lost the top-5 race in the
cross-corpus question; correct-but-incomplete, honestly hedged by the model.

## Constants

40 questions in 1.2 min; ~27k prompt tokens total; number warnings 0;
per-question context 1-3% of the 32k window. Deep plants (pages 44/61/77 of
80) all retrieved #1 again with wide margins.
