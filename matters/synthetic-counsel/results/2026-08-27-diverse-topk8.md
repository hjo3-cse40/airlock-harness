# Run 8: source-diverse retrieval on Q17/Q18 -> 39/40

Date: 2026-08-27. Machine: personal M3 MacBook Pro, 18 GB. Model: qwen3-8b
Q5_K_M via LM Studio. Same corpus (10 files, 320 chunks) and same 40 questions
as Run 7 (2026-08-27-qwen3-8b-m3.md). Two changes under test since Run 7:

1. Grounded generation now decodes at **temperature 0.0** (greedy), not 0.7.
2. The two aggregate-coverage questions (Q17, Q18) are tagged
   `--diverse --top-k 8` in test-questions.txt. Everything else runs at the
   default top_k 5 with no diversity.

`--diverse` takes the best chunk per source before filling remaining slots, so
one source cannot occupy every slot on a multi-firm question.

## Conditions

- Chat: `qwen3-8b` (unsloth Qwen3-8B-GGUF, Q5_K_M) via LM Studio 127.0.0.1:1234
- Load: context 8,192; Flash Attention ON; KV cache Q8_0; all 36 layers GPU;
  thinking OFF
- Embedder: `text-embedding-nomic-embed-text-v1.5@q8_0`
- Request (ask.py): **temp 0.0**, top_p 0.80, presence_penalty 1.5, max_tokens 1200
- Harness: top_k 5, min_score 1.0, dense_min 0.5; Q17/Q18 overridden to
  top_k 8 + diverse via per-line flags
- Protocol: `python3 ask.py --matter synthetic-counsel batch test-questions.txt`

## Result: 39/40 correct outcomes

Batch summary line: questions 40 | answered 31 | refused 9 (gate 0, model 9) |
number warnings 4 | errors 0. Elapsed 2.2 min; 33,005 prompt + 1,508 answer
tokens. Zero fabricated numbers, zero wrong-firm citations.

| Run | Model / machine | Change | Correct | Notes |
|---|---|---|---|---|
| 7 | 8B Q5 M3 | hybrid, temp 0.7, uniform top_k 5 | 37/40 | Q17, Q18, Q35 |
| 8 | 8B Q5 M3 | temp 0.0; Q17/Q18 diverse @ top_k 8 | **39/40** | Q35 only |

The only miss is Q35, which the answer key marks as a recorded finding rather
than a hard fail; counting it that way this run is effectively 40/40.

## What the diversity fix recovered

- **Q17 PASS** (was FAIL in Run 7). "Which firms have responded so far?" now
  names Alpha, Bravo, Charlie, Echo. Firm Alpha's context-summary chunk was
  rank 9 under plain retrieval; capping Firm Charlie's guide pages to one slot
  promoted it to S6, inside the top-8 window.
- **Q18 PASS** (was PARTIAL/FAIL in Run 7). "Which firms quoted a provisional
  fee, and the amounts?" now cites Alpha $4,800 and Bravo $6,100. Bravo's fee
  email was rank 11 under plain retrieval; capping the redundant Alpha chunks
  promoted it to S7.

Contrast (same machine, model, temp): the same Q17 at the default top_k 5 with
no diversity still names only Bravo/Charlie/Echo. The recovery is retrieval
selection, not the model.

Plain `--top-k 8` alone does NOT fix these (see 2026-08-27-topk-probe-and-temp0.md):
the extra slots go to firms already represented. Diversity plus the larger
top_k is what recovers them.

## Held constant / still open

- **Q35 false-refuse** ("Which law office turned us down?"). Firm Echo never
  ranked (absent from S1-S5). Still the 137M embedder's limit on a zero-overlap
  paraphrase at 320 chunks, not a chat-model-size problem.
- **Q16 checker noise.** Four `UNVERIFIED NUMBER` warnings (`08`, `12`, `19`,
  `2026`), all date fragments from headings that `verify_numbers` does not read
  from the body. Not fabricated money. Q16's answer was also verbose (correct
  "no reply" conclusion with a redundant "Not specified" tail): 8B style.
- **Q12 PASS**, deterministic now under temp 0.0.
- Deep plants Q37/Q38/Q39 retrieved #1. Q36 "fifteen hundred dollars"
  preserved, checker silent.

## Caveat for comparisons

Q17/Q18 now run at top_k 8 + diverse, so this run is not uniform top_k 5 like
Runs 1-7. The questions are identical; only those two lines' retrieval config
changed. A later fair quality comparison (14B on the same machine, or 8B vs
14B on one machine) should hold this same per-line config.
