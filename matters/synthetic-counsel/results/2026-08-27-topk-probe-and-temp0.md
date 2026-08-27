# Top-k probe (Q17/Q18) + temperature sweep -> temp 0.0

Date: 2026-08-27. Machine: personal M3 MacBook Pro, 18 GB. Model: qwen3-8b
Q5_K_M via LM Studio. This note records two experiments run on the public
mirror and the exact configuration to reproduce them on another machine.

## 1. Top-k probe: raising top_k does NOT fix aggregate coverage

On-record prediction was that `--top-k 8` would recover Q17 and Q18. It does
not. Tested Q17/Q18 at top_k 5, 8, and 15 (entries in audit.jsonl):

- **Q17 "Which firms have responded so far?"** (should name Alpha, Bravo,
  Charlie, Echo). top_k 5 and top_k 8 both name only Bravo/Charlie/Echo. The
  3 extra slots at top_k 8 were filled by low-relevance Firm Charlie *guide*
  pages (bm25 0.35, surviving on the cosine floor). Firm Alpha's chunk does
  not appear until **rank 9**.
- **Q18 "Which firms quoted a provisional fee, and the amounts?"** (Bravo =
  $6,100). top_k 5 and 8 both return "Bravo amount not specified." The 3 extra
  slots at top_k 8 were filled with *more Firm Alpha* chunks. Bravo's fee
  email does not appear until **rank 11**.

**Conclusion:** the binding constraint is not slot count, it is per-source
ranking diversity. Chunks from firms already represented crowd out the one
chunk carrying the missing firm. Raising top_k just adds more of the firms
already present. The fix is per-source diversity in selection (one best chunk
per firm, then fill), not a larger top_k.

## 2. Temperature sweep: accuracy flat, so temp 0.0 for reproducibility

Swept temperature 0.0 -> 0.7 in 0.1 steps, 20 samples per cell, 4 question
types (stable factual, the Q12 refuse-flip, a refuse-trap, a disambiguation).
640 calls, run twice, identical results both times.

| temp | Q1 | Q12 | Q28 | Q30 | avg | distinct(sum) |
|------|----|-----|-----|-----|-----|---------------|
| 0.0  | 100| 100 | 100 | 100 | 100 | 4  |
| 0.1  | 100| 100 | 100 | 100 | 100 | 6  |
| 0.2  | 100| 100 | 100 | 100 | 100 | 7  |
| 0.3  | 100| 100 | 100 | 100 | 100 | 10 |
| 0.4  | 100| 100 | 100 | 100 | 100 | 11 |
| 0.5  | 100| 100 | 100 | 100 | 100 | 12 |
| 0.6  | 100| 100 | 100 | 100 | 100 | 13 |
| 0.7  | 100| 100 | 100 | 100 | 100 | 11 |

Accuracy is identical at every temperature. The only thing that changes is
wording variety (`distinct`): temp 0.0 is the only fully deterministic point
(one identical answer per question). The Q12 flip did **not** reproduce on 8B
at any temperature: this confirms the flip is a 14B behavior. Default is now
`temperature: 0.0` in ask.py (greedy) for a reproducible audit trail. See
`temp_sweep.py` / `temp_sweep_raw.json`.

## Exact reproduction config (use this on the work laptop)

Full stack, one line per setting, so runs are apples-to-apples:

- Model: `qwen3-8b` (unsloth Qwen3-8B-GGUF, quant **Q5_K_M**)
- Server: LM Studio OpenAI endpoint at `127.0.0.1:1234`
- Context length: **8192**
- Flash Attention: **ON**
- KV cache quantization: **Q8_0**
- GPU offload: **all 36 layers**
- Thinking / reasoning: **OFF**
- Embedder: `text-embedding-nomic-embed-text-v1.5@q8_0` (must match the index)
- Request params (in ask.py): **temperature 0.0**, top_p 0.80, presence_penalty 1.5, max_tokens 1200
- Harness flags: top_k 5, min_score 1.0, dense_min 0.5 (all defaults)
- Command: `python3 ask.py --matter synthetic-counsel batch test-questions.txt`

## Planned work-laptop tests (2026-08-27)

1. **14B at temp 0.0 (flip test).** Same config as above but model
   `qwen3-14b` Q5_K_M. Goal: confirm temp 0.0 removes the Q12 run-to-run flip
   on the model where the flip actually appears.
2. **8B on the work laptop (same-machine benchmark).** Exact config above,
   model qwen3-8b Q5_K_M. Goal: de-confound Run 7's 92.5% (which mixed model
   swap + machine swap) by comparing 8B vs 14B on one machine, and 8B on M5
   vs 8B on M3 for the machine-only delta.
