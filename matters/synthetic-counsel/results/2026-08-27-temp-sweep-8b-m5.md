# Temperature sweep: Qwen3-8B Q5_K_M on work M5 Pro (24 GB)

Date: 2026-08-27. One full 40-question batch per temperature, temps 0.0-0.7.
Drives the real `ask.ask()` pipeline (retrieval + two-key gate + prompt +
number check + audit); only chat temperature varies (monkeypatched generate,
non-streaming). Auto-scored against ANSWER-KEY.md; self-check confirmed temp 0.0
reproduces the known 39/40 with Q35 the sole miss.

## Configuration (held constant)

- Machine: work M5 Pro, 24 GB unified
- Model: `qwen3-8b` (unsloth Qwen3-8B-GGUF, Q5_K_M) via LM Studio 127.0.0.1:1234
- Embedder: `text-embedding-nomic-embed-text-v1.5@q8_0` (hybrid RRF, W_DENSE 0.5)
- Load: context 8,192; Flash Attention ON; KV cache Q8_0; all 36 layers GPU;
  thinking OFF; Max Concurrent Predictions 1
- Request: top_p 0.80, presence_penalty 1.5, max_tokens 1200
- Harness: top_k 5, min_score 1.0, dense_min 0.5; Q17/Q18 use `--diverse --top-k 8`
- N = 1 batch per temperature (temp 0.0 deterministic; temps > 0 single samples)

## Results

| Temp | Correct | Fails      | Number warnings | tok/s |
|------|---------|------------|-----------------|-------|
| 0.0  | 39/40   | Q35        | 9               | 39.9  |
| 0.1  | 38/40   | Q16, Q35   | 8               | 37.3  |
| 0.2  | 39/40   | Q35        | 5               | 37.6  |
| 0.3  | 38/40   | Q16, Q35   | 4               | 37.3  |
| 0.4  | 39/40   | Q35        | 10              | 37.3  |
| 0.5  | 38/40   | Q31, Q35   | 5               | 37.4  |
| 0.6  | 38/40   | Q8, Q35    | 4               | 37.3  |
| 0.7  | 38/40   | Q31, Q35   | 4               | 37.0  |

Zero fabricated numbers and zero wrong-firm citations at every temperature.

## Findings

1. Accuracy is temperature-invariant on this corpus (38-39/40 at every setting).
   The pipeline carries reliability, not the sampling temperature.
2. Q35 fails at EVERY temperature: a persistent retrieval miss (paraphrase
   "turned us down" + stopword-invisible single-letter "Echo"; the Echo
   declination is never retrieved). Fix = stronger embedder or an alias/
   attribution guard, NOT temperature and NOT a bigger model.
3. The second failure is stochastic and moves (Q16, Q31, Q8 at different temps).
   Temps > 0 are single samples, so each is one draw, not a per-temp verdict.
4. Temperature 0 is the best operating point: same top score (39/40), fully
   reproducible, no random extra flip. No accuracy reason to run hot.
5. Speed stable ~37-40 tok/s, no thermal throttling across ~58 min.

## Caveats / next

- Single sample per temp > 0. To characterise variance, re-run N samples per
  temp (retrieval is deterministic, so only the chat call repeats).
- For an apples-to-apples 8B-vs-14B quality number, re-run this SAME sweep with
  the 14B loaded (same current test-questions.txt, temp 0). The old "~88%" 14B
  figure used different conditions (temp 0.7, pre-diverse questions).
- Raw per-question answers saved to scratchpad `sweep_results.json` at run time.
