#!/usr/bin/env python3
"""Temperature sweep experiment (throwaway, not part of the harness).

Reuses ask.py retrieval + prompt verbatim and varies ONLY temperature, to find
the accuracy sweet spot across a mix of question types. Retrieval is run once
per question (it is deterministic); every sample is a pure chat call so the only
moving part is temperature.

Usage:
  python3 temp_sweep.py --smoke     # 1 sample/question at temp 0, prints raw text
  python3 temp_sweep.py             # full sweep
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

import ask

MATTER = "synthetic-counsel"
TEMPS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
N = 20                 # samples per (question, temperature)
MAX_TOKENS = 256       # answers here are short; cap bounds any runaway thinking

THINK = re.compile(r"<think>.*?</think>", re.S)


def strip_think(t):
    return THINK.sub("", t).strip()


# ---- classifiers: return "correct" | "wrong" | "ambiguous" ----

def cls_factual_alpha(ans):
    # Q1: Firm Alpha provisional fee -> must state $4,800.
    return "correct" if re.search(r"4,?800", ans.lower()) else "wrong"


def cls_charlie_refuse(ans):
    # Q12 (--only firm-charlie): Charlie quoted NO provisional fee -> must refuse.
    # Drifting to any dollar figure (the $130 gov fee, etc.) is the documented fail.
    a = ans.lower()
    fee = bool(re.search(r"\$\s?\d", a)) or bool(re.search(r"\b130\b|\b364\b|\b500\b", a)) or bool(re.search(r"4,?800", a))
    refuse = any(m in a for m in [
        "not in the documents", "not specified", "no fee", "did not quote",
        "didn't quote", "not quote", "no provisional fee", "not provided",
        "pending", "conflicts check", "no quote", "has not quoted",
        "hasn't quoted", "not stated", "does not specify", "doesn't specify",
        "no specific fee", "not given", "no amount"])
    if fee:
        return "wrong"
    if refuse:
        return "correct"
    return "ambiguous"


def cls_charlie_trap(ans):
    # Q28: "Did Firm Charlie quote $4,800?" ($4,800 is Alpha's) -> must NOT say yes.
    a = ans.lower()
    if re.search(r"\byes\b", a):
        return "wrong"
    if any(m in a for m in ["no,", "no.", " no ", "did not", "didn't", "not quote",
                            "alpha", "not in the documents", "cannot confirm",
                            "no fee", "not stated", "not specified", "incorrect",
                            "is not correct", "that is not", "no record"]):
        return "correct"
    return "ambiguous"


def cls_perpatent(ans):
    # Q30: $19,500 is PER PATENT (program total is $340,000).
    a = ans.lower()
    if "per patent" in a:
        return "correct"
    if "total" in a:
        return "wrong"
    return "ambiguous"


QUESTIONS = [
    ("Q1  factual (stable control)", "What fee did Firm Alpha quote for a provisional filing?", None, cls_factual_alpha),
    ("Q12 refuse (known flip)",      "What fee was quoted for a provisional filing?", "firm-charlie", cls_charlie_refuse),
    ("Q28 refuse-trap",              "Did Firm Charlie quote $4,800 for a provisional?", None, cls_charlie_trap),
    ("Q30 disambiguation",           "Is the Firm Alpha estimate $19,500 per patent or $19,500 total?", None, cls_perpatent),
]


def build_context(index, emb_model, question, only):
    chunks = index["chunks"]
    if only:
        chunks = [c for c in chunks if c["file"].startswith(only)]
    hits, _bm, _cos = ask.hybrid(chunks, question, 5, index["chunks"] if only else None, emb_model)
    hits = [(s, cs, c) for s, cs, c in hits if s > 0 or (cs or 0) > 0]
    src = [f"[S{i}] {c['file']} > {c['heading'] or '(no heading)'}\n{c['text']}"
           for i, (s, cs, c) in enumerate(hits, 1)]
    return "Sources:\n\n" + "\n\n".join(src) + f"\n\n---\nQuestion: {question}"


def chat(system, user, model, temp):
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": temp, "top_p": 0.8, "presence_penalty": 1.5,
        "max_tokens": MAX_TOKENS, "stream": False,
    }
    req = urllib.request.Request(ask.SERVER + "/chat/completions",
                                 json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        obj = json.load(r)
    return strip_think(obj["choices"][0]["message"]["content"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("-n", type=int, default=N)
    a = ap.parse_args()

    index = ask.load_index(MATTER)
    chat_model, emb_model = ask.server_models()
    if not chat_model:
        sys.exit("LM Studio server offline.")
    if not index.get("embed_model"):
        emb_model = None
    system = open(os.path.join(ask.BASE, "prompt.txt"), encoding="utf-8").read()

    contexts = {label: build_context(index, emb_model, q, only)
                for (label, q, only, _cls) in QUESTIONS}

    if a.smoke:
        for (label, q, only, clsf) in QUESTIONS:
            ans = chat(system, contexts[label], chat_model, 0.0)
            print(f"\n### {label}  [{clsf(ans)}]\n{ans}")
        return

    n = a.n
    print(f"temp sweep: model={chat_model}  temps={TEMPS}  n={n}/cell  "
          f"({len(TEMPS)*len(QUESTIONS)*n} calls)\n")
    raw = {}
    t_start = time.time()
    # tally[temp][label] = {"correct":x,"wrong":y,"ambiguous":z,"answers":set}
    tally = {t: {label: {"correct": 0, "wrong": 0, "ambiguous": 0, "distinct": set()}
                 for (label, *_r) in QUESTIONS} for t in TEMPS}
    for temp in TEMPS:
        for (label, q, only, clsf) in QUESTIONS:
            for _ in range(n):
                ans = chat(system, contexts[label], chat_model, temp)
                verdict = clsf(ans)
                tally[temp][label][verdict] += 1
                tally[temp][label]["distinct"].add(ans[:120])
                raw.setdefault(f"{temp}|{label}", []).append(ans)
            cell = tally[temp][label]
            print(f"  temp {temp:.1f}  {label:32s} "
                  f"correct {cell['correct']:2d}/{n}  wrong {cell['wrong']:2d}  "
                  f"amb {cell['ambiguous']:2d}  distinct {len(cell['distinct'])}")
        print()

    with open(os.path.join(ask.BASE, "temp_sweep_raw.json"), "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=1)

    # ---- summary ----
    print("=" * 74)
    print("SUMMARY  (correct% per question, and overall average, by temperature)")
    print("=" * 74)
    header = "temp | " + " | ".join(f"{lbl.split()[0]:>4}" for (lbl, *_r) in QUESTIONS) + " |  AVG   distinct(sum)"
    print(header)
    print("-" * len(header))
    best_t, best_avg = None, -1.0
    for temp in TEMPS:
        pcts, dsum = [], 0
        for (label, *_r) in QUESTIONS:
            c = tally[temp][label]
            pct = 100.0 * c["correct"] / n
            pcts.append(pct)
            dsum += len(c["distinct"])
        avg = sum(pcts) / len(pcts)
        if avg > best_avg:
            best_avg, best_t = avg, temp
        cells = " | ".join(f"{p:4.0f}" for p in pcts)
        print(f" {temp:.1f} | {cells} | {avg:5.1f}   {dsum}")
    print("-" * len(header))
    print(f"\nBest average accuracy: temp {best_t:.1f} at {best_avg:.1f}%")
    print(f"elapsed {(time.time()-t_start)/60:.1f} min   raw -> temp_sweep_raw.json")


if __name__ == "__main__":
    main()
