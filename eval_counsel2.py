#!/usr/bin/env python3
"""Deterministic CORRECT / SILENT / WRONG scorer for a counsel-2 run. No LLM judge.

  python3 eval_counsel2.py [--tag test-questions.txt] [--since "2026-09-10 12:00"] [--verbose]
                           [--envelope] [--release NAME]
  python3 eval_counsel2.py --compare runA.json runB.json [labelA labelB]   # paired two-run comparison
      (each file is {question: audit record}; prints per-class discordance + exact McNemar)
  --document-scope   read must_not / forbid_amounts / forbidden names over the whole answer (old rule)

Sentence scope (default): a sentence that carries an exclusion cue (not, no, never, only, rather
than, separate, distinct, different, except, but, n't) is skipped by must_not, forbid_amounts and
the forbidden-name check, so an answer that names a neighbouring figure or firm in order to rule
it out is not scored as having given it. Measured 2026-09-10: the whole-answer rule turned 3 of
Gemma's 9 WRONG and 11 of Qwen's 20 into verbosity penalties.

Reads matters/counsel-2/answer-key.json, index.json, source.json (firm aliases) and every
audit/*.jsonl. Ask-mode items match (batch == tag, normalized question), last line wins.
Reason-mode items match (mode == reason, normalized question, ts >= --since).

Resolution order per item (SPEC-DRAFT section 8):
  WRONG    missing audit line, or an `error` field, or any must_not token, or a must_not_unless
           token with no licence, or forbid_cooccur / forbid_amounts violated, or a forbidden
           name (name_set_exact), or number_locality failed, or a forged [S#] label, or a cited
           number that lives only in a cite_must_not file, or an amount that is in no index chunk.
  CORRECT  not WRONG, and every must, one of each any-group, every required name, every
           cite_must fragment, every expect_warning, no forbid_warning, and (type refuse) a
           refusal or the required negative assertion.
  SILENT   everything else: refused, hedged, incomplete, or right but unsourced.

Headline: silent-wrong rate = WRONG items whose audit line carries no warning, over N, with a
Wilson 95% interval. Also: false-refusal rate, mis-cited-number count, forged-label count,
per-class k/n, pair-level counts. --envelope writes ENVELOPE.md with the rates and NO verdict
(the verdict thresholds are an open question until a few releases exist)."""
import glob, hashlib, json, math, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_thread_probe import REFUSAL_PATTERNS, norm, num_variants, present, is_refusal  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
MATTER = os.path.join(BASE, "matters", "counsel-2")
AMOUNT_RE = re.compile(r"(?i)(?:[$€]\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*(?:\.\d+)?\s*(?:dollars?|usd|eur|euros?)\b|\b\d{1,3}(?:,\d{3})+\b)")
LABEL_RE = re.compile(r"\[S(\d+)(?:\s*,\s*S?(\d+))*\]|\[S(\d+)\]")
SENT_SPLIT = re.compile(r"(?<=[.!?\n])\s+|\n")
NEG_EXT = ("unable to refer", "no referral", "did not name", "not quoted", "does not publish", "no flat",
           "indicative", "not a quote", "no figure", "did not quote", "only says per application",
           "does not say", "not specified", "which firm", "cannot tell", "not clear", "no previous",
           "ambiguous", "on its own", "no such", "no decision", "not selected", "nobody", "still open")


def labels_in(s):
    out = []
    for m in re.finditer(r"\[S([\d,\sS]+)\]", s):
        out += [int(x) for x in re.findall(r"\d+", m.group(1))]
    return out

def amounts_in(s):
    return [m.group(0) for m in AMOUNT_RE.finditer(s)]

def bare(n):
    return re.sub(r"[^\d.]", "", n).rstrip(".")

def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))

def load_audit():
    recs = []
    for p in sorted(glob.glob(os.path.join(MATTER, "audit", "*.jsonl"))):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    recs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return recs

class Names:
    """Word-boundary firm-name matching with an alias table; 'Alpha IP Group' never counts as 'Alpha'."""
    def __init__(self, parties):
        self.alias = {}
        self.not_alias = {}
        for p in parties:
            key = p["name"].replace("Firm ", "")
            self.alias[key] = list(dict.fromkeys([p["name"], key] + (p.get("aliases") or [])))
            self.not_alias[key] = p.get("not_aliases") or []
    def present(self, name, answer):
        key = name.replace("Firm ", "")
        text = answer
        for na in self.not_alias.get(key, []):
            text = re.sub(re.escape(na), " ", text, flags=re.I)
        for a in self.alias.get(key, [name]):
            if re.search(r"(?<![A-Za-z])" + re.escape(a) + r"(?![A-Za-z])", text, flags=re.I):
                return True
        return False


SENTENCE_SCOPE = True    # default since 2026-09-10; --document-scope restores the old whole-answer reading
NEG_CUE = re.compile(r"(?i)\b(not|no|never|neither|nor|only|rather than|instead of|separate|distinct|different|unaffiliated|excluding|excluded|except|but)\b|\bn't\b")

def _scoped(ans):
    """Sentences of the answer that carry NO exclusion cue: the text a document-wide check
    should read when the answer names a neighbour only to rule it out."""
    return " ".join(s for s in SENT_SPLIT.split(ans) if s.strip() and not NEG_CUE.search(s))

def score_item(q, r, index_chunks, index_numbers, names):
    """Returns (label, reasons, flags) where flags = {silent_wrong, mis_cited, forged, false_refusal}."""
    why, flags = [], {"mis_cited": False, "forged": False}
    if r is None:
        return "WRONG", ["no audit line"], flags
    if r.get("error"):
        return "WRONG", [f"audit line carries error: {str(r['error'])[:80]}"], flags
    ans = r.get("answer") or ""
    a = norm(ans)
    chunks = r.get("chunks") or []
    warnings = r.get("warnings") or []
    refused = bool(r.get("refused")) or is_refusal(ans) or any(p in a for p in NEG_EXT)
    wrong = False
    # ---- WRONG conditions ----
    scope_raw = _scoped(ans) if SENTENCE_SCOPE else ans
    scope = norm(scope_raw)
    bad = [t for t in q.get("must_not") or [] if present(t, scope)]
    if bad:
        wrong = True; why.append(f"must_not present: {bad}")
    for tok, lic in q.get("must_not_unless") or []:
        if present(tok, a) and not any(present(l, a) for l in lic):
            wrong = True; why.append(f"'{tok}' without a licence token {lic}")
    sents = [s for s in SENT_SPLIT.split(ans) if s.strip()]
    for tok, rx in q.get("forbid_cooccur") or []:
        for s in sents:
            if present(tok, norm(s)) and re.search(rx, s, flags=re.I):
                wrong = True; why.append(f"'{tok}' co-occurs with /{rx}/ in one sentence"); break
    amts = amounts_in(ans)
    amts_scoped = amounts_in(scope_raw)
    if q.get("forbid_amounts") and amts_scoped and not (isinstance(q["forbid_amounts"], str)):
        wrong = True; why.append(f"amount given where none is allowed: {amts_scoped}")
    nse = q.get("name_set_exact")
    if nse:
        forbidden = [n for n in nse.get("must_not") or [] if names.present(n, scope_raw)]
        if forbidden:
            wrong = True; why.append(f"forbidden name(s): {forbidden}")
    labels = labels_in(ans)
    if q.get("label_valid", True) and any(l < 1 or l > len(chunks) for l in labels):
        wrong = True; flags["forged"] = True; why.append(f"forged label: [S{[l for l in labels if l < 1 or l > len(chunks)][0]}] of {len(chunks)} sources")
    if q.get("number_locality") and chunks and not refused:
        for s in sents:
            ls = [l for l in labels_in(s) if 1 <= l <= len(chunks)]
            if not ls:
                continue
            pool = " ".join(index_chunks.get(chunks[l - 1]["id"], "") for l in ls).replace(",", "")
            for n in amounts_in(s):
                b = bare(n)
                if b and b not in pool:
                    wrong = True; flags["mis_cited"] = True
                    why.append(f"{n} not in the chunk it cites [S{ls}]"); break
    if any("MIS-CITED NUMBER" in w for w in warnings):
        flags["mis_cited"] = True
        if not wrong:
            why.append("harness MIS-CITED NUMBER warning (not scored WRONG by locality here)")
    for frag in q.get("cite_must_not") or []:
        for n in amts:
            b = bare(n)
            holders = [c for c in chunks if b and b in index_chunks.get(c["id"], "").replace(",", "")]
            if holders and all(frag in c["file"] for c in holders):
                wrong = True; why.append(f"{n} is sourced only from {frag}"); break
    if not refused:
        for n in amts:
            b = bare(n)
            if b and re.fullmatch(r"\d{3,}(?:\.\d+)?", b) and b not in index_numbers:
                wrong = True; why.append(f"{n} appears in no index chunk (fabrication)"); break
    if wrong:
        return "WRONG", why, flags
    # ---- CORRECT conditions ----
    ok = True
    miss = [t for t in q.get("must") or [] if not present(t, a)]
    if miss:
        ok = False; why.append(f"missing must: {miss}")
    miss_any = [g for g in q.get("any") or [] if not any(present(t, a) for t in g)]
    if q["type"] == "refuse" and refused:
        miss_any = []   # a refusal satisfies a refuse item's any-groups; they describe the ALTERNATIVE negative assertion
    if miss_any:
        ok = False; why.append(f"missing any-group: {miss_any[0]}" + (f" (+{len(miss_any)-1})" if len(miss_any) > 1 else ""))
    if nse:
        missing_names = [n for n in nse.get("must") or [] if not names.present(n, ans)]
        if missing_names:
            ok = False; why.append(f"missing name(s): {missing_names}")
    files = [c.get("file") or "" for c in chunks]
    miss_cite = [f for f in q.get("cite_must") or [] if not any(f in x for x in files)]
    if miss_cite:
        ok = False; why.append(f"expected source not among cited chunks: {miss_cite}")
    miss_w = [w for w in q.get("expect_warning") or [] if not any(w in x for x in warnings)]
    if miss_w:
        ok = False; why.append(f"expected warning missing: {miss_w}")
    hit_w = [w for w in q.get("forbid_warning") or [] if any(w in x for x in warnings)]
    if hit_w:
        ok = False; why.append(f"forbidden warning fired: {hit_w}")
    if q["type"] == "refuse":
        if not refused and miss_any:
            ok = False; why.append("answered without the required negative assertion")
    else:
        has_required = bool((q.get("must") or []) or (q.get("any") or []) or nse)
        if refused and (not has_required or miss or miss_any):
            ok = False; why.append("REFUSED")
    if ok:
        return "CORRECT", why, flags
    return "SILENT", why, flags


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p over the discordant pairs (b: A right, B wrong; c: the reverse)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * p)

def compare(path_a, path_b, key, index_chunks, index_numbers, names, label_a="A", label_b="B"):
    """Paired comparison of two runs saved as {question: audit record} JSON snapshots.
    Prints per-class discordance and the exact McNemar p on CORRECT vs not-CORRECT and on
    WRONG vs not-WRONG. Item 100-style label flips are the caller's problem to read."""
    A = json.load(open(path_a, encoding="utf-8")); B = json.load(open(path_b, encoding="utf-8"))
    rows = []
    for q in key:
        if q.get("mode") == "reason":
            continue
        ra, rb = A.get(q["text"]), B.get(q["text"])
        la = score_item(q, ra, index_chunks, index_numbers, names)[0]
        lb = score_item(q, rb, index_chunks, index_numbers, names)[0]
        rows.append((q, la, lb))
    n = len(rows)
    tot = {label_a: {"CORRECT": 0, "SILENT": 0, "WRONG": 0}, label_b: {"CORRECT": 0, "SILENT": 0, "WRONG": 0}}
    for _, la, lb in rows:
        tot[label_a][la] += 1; tot[label_b][lb] += 1
    print(f"paired comparison over {n} ask-mode items: {label_a} {tot[label_a]}   {label_b} {tot[label_b]}")
    b_c = sum(1 for _, la, lb in rows if la == "CORRECT" and lb != "CORRECT")
    c_c = sum(1 for _, la, lb in rows if la != "CORRECT" and lb == "CORRECT")
    b_w = sum(1 for _, la, lb in rows if la != "WRONG" and lb == "WRONG")
    c_w = sum(1 for _, la, lb in rows if la == "WRONG" and lb != "WRONG")
    print(f"CORRECT: {label_a}-only {b_c}, {label_b}-only {c_c}, exact McNemar p = {mcnemar_exact(b_c, c_c):.3f}")
    print(f"WRONG:   {label_b}-only {b_w}, {label_a}-only {c_w}, exact McNemar p = {mcnemar_exact(b_w, c_w):.3f}")
    print("\n| class | n | " + f"{label_a} C/S/W | {label_b} C/S/W | discordant |")
    print("|---|---|---|---|---|")
    by = {}
    for q, la, lb in rows:
        d = by.setdefault(q["category"], {"n": 0, "a": [0, 0, 0], "b": [0, 0, 0], "disc": 0})
        d["n"] += 1
        for lab, key_ in ((la, "a"), (lb, "b")):
            d[key_][["CORRECT", "SILENT", "WRONG"].index(lab)] += 1
        d["disc"] += la != lb
    for cat, d in by.items():
        print(f"| {cat} | {d['n']} | {'/'.join(map(str, d['a']))} | {'/'.join(map(str, d['b']))} | {d['disc']} |")
    print("\ndiscordant items:")
    for q, la, lb in rows:
        if la != lb:
            print(f"  #{q['n']:>3} [{q['category']}] {la:7} -> {lb:7} {q['text'][:70]}")

def main():
    global SENTENCE_SCOPE
    args = sys.argv[1:]
    if "--document-scope" in args:
        SENTENCE_SCOPE = False
        print("DOCUMENT SCOPE: must_not, forbid_amounts and forbidden names read the whole answer (pre-2026-09-10 rule)")
    if "--compare" in args:
        i = args.index("--compare")
        key = json.load(open(os.path.join(MATTER, "answer-key.json"), encoding="utf-8"))["questions"]
        index = json.load(open(os.path.join(MATTER, "index.json"), encoding="utf-8"))
        src = json.load(open(os.path.join(MATTER, "source.json"), encoding="utf-8"))
        ic = {c["id"]: (c.get("heading") or "") + "\n" + (c.get("text") or "") for c in index["chunks"]}
        nums = set()
        for t in ic.values():
            for n in re.findall(r"\d[\d,]*(?:\.\d+)?", t):
                nums.add(n.replace(",", ""))
        la = args[i + 3] if len(args) > i + 3 and not args[i + 3].startswith("--") else "A"
        lb = args[i + 4] if len(args) > i + 4 and not args[i + 4].startswith("--") else "B"
        compare(args[i + 1], args[i + 2], key, ic, nums, Names(src["parties"]), la, lb)
        return
    def opt(name, default=None):
        return args[args.index(name) + 1] if name in args else default
    tag = opt("--tag", "test-questions.txt")
    since = opt("--since", "")
    release = opt("--release", "unreleased")
    verbose = "--verbose" in args
    key = json.load(open(os.path.join(MATTER, "answer-key.json"), encoding="utf-8"))["questions"]
    index = json.load(open(os.path.join(MATTER, "index.json"), encoding="utf-8"))
    src = json.load(open(os.path.join(MATTER, "source.json"), encoding="utf-8"))
    names = Names(src["parties"])
    index_chunks = {c["id"]: (c.get("heading") or "") + "\n" + (c.get("text") or "") for c in index["chunks"]}
    index_numbers = set()
    for t in index_chunks.values():
        for n in re.findall(r"\d[\d,]*(?:\.\d+)?", t):
            index_numbers.add(n.replace(",", ""))
    recs = load_audit()
    ask_recs, reason_recs = {}, {}
    for r in recs:
        if "question" not in r:
            continue
        if r.get("mode") == "reason":
            if not since or (r.get("ts") or "") >= since:
                reason_recs[norm(r["question"])] = r
        elif r.get("batch") == tag:
            ask_recs[norm(r["question"])] = r
    rows, by_class, pairs = [], {}, {}
    n_correct = n_silent = n_wrong = n_sw = n_fr = n_mc = n_fg = 0
    models = set()
    for q in key:
        pool = reason_recs if q.get("mode") == "reason" else ask_recs
        r = pool.get(norm(q["text"]))
        label, why, fl = score_item(q, r, index_chunks, index_numbers, names)
        warned = bool((r or {}).get("warnings"))
        if r:
            models.add(r.get("model") or (r.get("config") or {}).get("chat_model") or "?")
        if label == "CORRECT":
            n_correct += 1
        elif label == "SILENT":
            n_silent += 1
            if q["type"] != "refuse" and any(w.startswith("REFUSED") for w in why):
                n_fr += 1
        else:
            n_wrong += 1
            if not warned:
                n_sw += 1
        n_mc += fl["mis_cited"]; n_fg += fl["forged"]
        c = by_class.setdefault(q["category"], {"n": 0, "CORRECT": 0, "SILENT": 0, "WRONG": 0, "silent_wrong": 0})
        c["n"] += 1; c[label] += 1; c["silent_wrong"] += (label == "WRONG" and not warned)
        if q.get("pair"):
            pairs.setdefault(q["pair"], []).append(label)
        ans = (r or {}).get("answer") or ""
        rows.append((q["n"], label, q["category"], q["text"], "; ".join(why), ans if verbose else ans[:140].replace("\n", " ")))
    N = len(key)
    core = [q for q in key if q["category"] != "reason"]
    n_core = len(core)
    widened = sum(1 for q in key if q.get("widened"))
    prompt_sha = hashlib.sha256(open(os.path.join(BASE, "prompt.txt"), "rb").read()).hexdigest()[:12]
    try:
        code_sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=BASE, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "ask.py", "prompt.txt", "reason-prompt.txt"], cwd=BASE, capture_output=True, text=True).stdout.strip()
        code_sha += "-dirty" if dirty else ""
    except OSError:
        code_sha = "?"
    key_sha = hashlib.sha256(open(os.path.join(MATTER, "answer-key.json"), "rb").read()).hexdigest()[:12]
    print(f"counsel-2 scorer  release={release}  tag={tag}  model(s)={', '.join(sorted(models)) or 'none'}")
    print(f"KEY {key_sha}  KEYS WIDENED: {widened}   prompt {prompt_sha}  code {code_sha} (scorer-side; audit lines carry no protocol hash yet)  index_built {index.get('built')}")
    print()
    for n, label, cat, text, why, ans in rows:
        print(f"{n:>3} {label:7} {cat:12} {text}")
        if why:
            print(f"    {why}")
        if verbose:
            print("    > " + ans.replace("\n", "\n    > "))
    print()
    lo, hi = wilson(n_sw, N)
    print(f"N={N}  CORRECT {n_correct} ({n_correct/N:.0%})  SILENT {n_silent} ({n_silent/N:.0%})  WRONG {n_wrong} ({n_wrong/N:.0%})")
    print(f"SILENT-WRONG {n_sw}/{N} = {n_sw/N:.1%}  Wilson95 [{lo:.1%}, {hi:.1%}]   (WRONG with an empty warnings list)")
    n_answerable = sum(1 for q in key if q["type"] != "refuse")
    print(f"false-refusal {n_fr}/{n_answerable}   mis-cited-number {n_mc}   forged-label {n_fg}")
    print()
    print("| class | n | correct | silent | wrong | silent-wrong |")
    print("|---|---|---|---|---|---|")
    for cat, c in by_class.items():
        print(f"| {cat} | {c['n']} | {c['CORRECT']} | {c['SILENT']} | {c['WRONG']} | {c['silent_wrong']} |")
    if pairs:
        pc = sum(1 for v in pairs.values() if all(x == "CORRECT" for x in v))
        pw = sum(1 for v in pairs.values() if any(x == "WRONG" for x in v))
        print(f"\npairs: {len(pairs)} total, {pc} both-correct, {pw} with a WRONG twin, {len(pairs)-pc-pw} silent")
    if "--envelope" in args:
        lines = [f"# Operating envelope, counsel-2, release {release}",
                 f"# code {code_sha}  prompt {prompt_sha}  key {key_sha}  index {index.get('built')}  model {', '.join(sorted(models))}",
                 f"# generated by eval_counsel2.py from {N} items ({n_core} core); rates only, no verdict until the thresholds are set",
                 "", "| class | n | correct | silent | wrong | silent-wrong |", "|---|---|---|---|---|---|"]
        for cat, c in by_class.items():
            lines.append(f"| {cat} | {c['n']} | {c['CORRECT']} | {c['SILENT']} | {c['WRONG']} | {c['silent_wrong']} |")
        lines += ["", f"silent-wrong rate {n_sw}/{N} = {n_sw/N:.1%}, Wilson 95% [{lo:.1%}, {hi:.1%}]",
                  f"false-refusal {n_fr}/{n_answerable}; mis-cited-number {n_mc}; forged-label {n_fg}; keys widened {widened}"]
        with open(os.path.join(MATTER, "ENVELOPE.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"\nwrote {os.path.relpath(os.path.join(MATTER, 'ENVELOPE.md'), BASE)}")

if __name__ == "__main__":
    main()
