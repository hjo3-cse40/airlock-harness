# Baseline run: 40-question mega-prompt stress test

Date: 2026-08-26. First recorded metric run for strata-airlock. Synthetic
corpus, so this file is shareable and can feed the SPIE pilot.

## Conditions

- Model: qwen3-14b (unsloth Qwen3-14B-GGUF, Q5_K_M) via LM Studio 127.0.0.1:1234
- Load: context 32,768; Flash Attention ON; KV cache Q8_0; all 40 layers GPU
- Request: temp 0.7, top_p 0.80, presence_penalty 1.5, max_tokens 1,200
- Harness: strata-v0 ask.py; top_k 5; min_score 1.0; no --only scoping
- Corpus: matters/synthetic-counsel, 10 files, 320 chunks (80-page guide dominant)
- Protocol: ALL 40 questions in ONE prompt = ONE retrieval pass for everything
  (deliberate overload; per-question ground truth in ../ANSWER-KEY.md)

## Headline numbers (the baseline)

| Metric | Value |
|---|---|
| Precision (claims made that were true + correctly cited) | **100% (12/12)** |
| Recall (answerable questions actually answered) | **45% (12 of 26 answerable... see note)** |
| Correct outcomes total (answers + correct refusals) | 18/40 (45%) |
| Fabricated or borrowed numbers | **0** |
| Wrong citations | 0 |
| False refusals (answerable but refused) | 22/40 |
| Correct refusals (questions 22-27, designed unanswerable) | 6/6 |
| Context used | 1,494 prompt + 583 answer = 2,077 / 32,768 (6%) |

Note on recall: 34 of 40 questions are answerable from the corpus; 12 answered
= 35% strict recall. The 45% figure counts correct outcomes over all 40. Use
"100% precision / 45% correct-outcome rate / 0 fabrications" as the quoted set.

## Per-question outcomes

- Correct + cited: 1, 2, 3, 4, 5, 6, 29, 30, 33, 34, 36 (12 incl. fee set)
- Correct refusals: 22, 23, 24, 25, 26, 27
- False refusals: 7-28 remainder, 31, 32, 35, 37-40 (everything needing
  Bravo / Charlie / Delta / Echo / guide / engagement-terms chunks)

## Why recall collapsed (expected, by design)

One retrieval for 40 questions: the term soup weighted Firm Alpha (~15/40
questions mention it), so all 5 chunks went firm-alpha + context-summary
(scores 86-137 vs ~14 in normal single-question runs). Every non-Alpha fact
was never shown to the model. Architecture lesson demonstrated: one call =
one retrieval = one question answered well.

## Notable individual results

- Q28 (trap): "Did Firm Charlie quote $4,800?" with Alpha's $4,800 visible in
  context and 39 distractor questions -> REFUSED (safe). No wrong "yes".
- Q36 (known-hard): source says "fifteen hundred dollars" with no numeral.
  Model preserved the wording verbatim; number check correctly stayed silent.
- Q33 (paraphrase): passed, with asterisk: Q1's word "provisional" in the same
  prompt bridged "temporary patent application". Re-test solo before crediting.
- 6% context use shows the harness CAPPED the load (5 chunks), not that the
  model handled a large load. Real long-context stress = rerun with
  --top-k 40/60 and watch recall vs context size.

## Headline sentence for reuse

Under a 40-question single-prompt overload, the cite-or-refuse harness
degraded SAFELY: zero fabrications, zero wrong citations, 100% precision;
all loss appeared as refusals (recall 45%). Failure mode = silence, not lies.

## Planned comparison runs (same 40 questions, same corpus)

1. Batch mode: one retrieval PER question. Expected: recall rises sharply at
   equal precision. This is the architecture argument in one table.
2. --top-k sweep (5/20/40/60) on the mega-prompt: recall vs context size.
3. Same runs at other quants (Q4/Q8) and models: the SPIE quantization axis.
