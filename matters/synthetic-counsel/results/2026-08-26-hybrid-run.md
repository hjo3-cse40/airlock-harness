# Run 5: first hybrid run (BM25 + nomic dense, equal-weight RRF)

Date: 2026-08-26. Same corpus (320 chunks), model, settings, 40 questions.
Change under test: dense retrieval active for the first time.
Embedder: text-embedding-nomic-embed-text-v1.5@q8_0 (137M, Q8_0, task
prefixes applied). Fusion: reciprocal rank fusion, k=60, EQUAL weight.
Gate: two-key (bm25 >= 1.0 OR cosine >= 0.5).

## Score: ~35/40, roughly flat vs run 4 (36/40), composition changed.

## Prediction scorecard (recorded before the run)

- Q15 FLIPPED as predicted: bm25 0.01 / cos 0.63 -> dense key unlocked the
  gate; Echo's conflict reason quoted verbatim. The two-key gate design works.
- Q35 DID NOT FLIP - diagnosis refined: the gate passed (cos 0.55) but
  ranking never surfaced the Echo email among 320 chunks; "law office turned
  us down" scored ~0.52-0.55 against many unrelated chunks. A 137M embedder
  cannot separate this paraphrase at corpus scale. Gate key != ranker.
- Q16 stayed refused as predicted (scoping-usage class, untouched).

## New churn: equal-weight dense degraded cross-corpus aggregates

Mid-cosine chunks displaced summary chunks BM25 had exactly right:
- Q17 regression: listed Charlie/Echo/Bravo, OMITTED Alpha (summary chunk
  pushed out of top 5).
- Q20 regression: the "Open questions" chunk fell out of top 5; model
  synthesized a plausible-but-wrong list from what it received.
- Q18 regression: "Firm Bravo has not quoted a provisional fee" - a
  misreading of the summary's "partial"; first materially wrong claim since
  Q12 (cited honestly, no fabricated number, still wrong).
- Q39 survived BECAUSE BM25 outvoted dense (dense preferred filler pages
  0.72 vs plant 0.68) - small-embedder noise made visible.

Constants held: zero fabrications, zero UNVERIFIED warnings, deep plants
still retrieved, 1.6 min for 40 questions.

## Finding

At this scale with a small embedder, dense retrieval is STRONG as a gate key
and WEAK-TO-HARMFUL as an equal-vote ranker. Calibration, not concept:
fusion weights were wrong.

## Next change (prediction on record)

Demote dense to half weight in RRF (BM25 = primary ranker; dense = gate key
+ tie-breaker). Predicted: Q17/Q18/Q20 recover run-4 answers; Q15 keeps its
win (gate key untouched); Q35 stays failed until a stronger embedder.
Expected ~37/40.
