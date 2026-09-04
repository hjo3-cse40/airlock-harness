"""Deterministic scorer for a thread-probe batch run.
Usage: python3 score_batch.py <answer-key.json> <audit.jsonl> <batch-tag> [--corpus-dir docs/] [--verbose]
answer-key.json = {"questions": [{n, text, type: fact|refuse|summary|list, must[], any[[..]], must_not[], facts[[..]], min_facts, cite, expected}]}
Matches audit lines by (batch == tag) and question text, LAST occurrence wins (a re-run overrides).
PASS rules:
  fact/list : answered (not a refusal) AND every must present AND one of each any-group present AND no must_not present
  refuse    : refusal text (gate or model) OR (answered but no must_not present and answer says not specified)
  summary   : answered AND at least min_facts fact-groups present AND no must_not present
Also reports: cited the expected file; UNVERIFIED NUMBER warnings; numbers in the answer that appear NOWHERE in the corpus (fabrication)."""
import json, re, sys, os, glob

REFUSAL_PATTERNS = ("not in the documents", "not specified in the sources", "not specified in the source",
                    "no information", "does not specify", "do not specify", "is not mentioned", "not mentioned",
                    "not stated", "not addressed", "did not write", "did not reply", "did not send", "no message from")

def norm(s):
    s = (s or "").lower().replace("’", "'").replace("“", '"').replace("”", '"')
    s = s.replace(" ", " ")
    return re.sub(r"\s+", " ", s)

def num_variants(tok):
    """'$12,500' -> {'$12,500','12,500','12500','12 500'}; 'may 7' -> {'may 7','may 7,','7 may'}"""
    t = norm(tok)
    out = {t}
    if re.fullmatch(r"\$?[\d,]+(?:\.\d+)?%?", t):
        bare = t.lstrip("$")
        out |= {bare, bare.replace(",", ""), "$" + bare.replace(",", "")}
    m = re.fullmatch(r"([a-z]+) (\d{1,2})", t)
    if m:
        out |= {f"{m.group(2)} {m.group(1)}", f"{m.group(1)} {m.group(2)}th", f"{m.group(1)} {m.group(2)}st", f"{m.group(1)} {m.group(2)}nd", f"{m.group(1)} {m.group(2)}rd"}
    return out

def present(tok, ans):
    t = norm(tok)
    if re.fullmatch(r"\d+", t):
        # a bare number must stand alone: 24 is not 2024, $2,400 or 24%-of-something's 124
        return re.search(r"(?<![\d,.$])" + re.escape(t) + r"(?![\d,])", ans) is not None
    return any(v in ans for v in num_variants(tok))

def is_refusal(ans):
    a = norm(ans)
    return any(p in a for p in REFUSAL_PATTERNS)

def corpus_numbers(corpus_dir):
    nums = set()
    for p in glob.glob(os.path.join(corpus_dir, "**", "*"), recursive=True):
        if os.path.isdir(p) or p.endswith((".pdf", ".eml")):
            continue
        try:
            txt = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for n in re.findall(r"\d[\d,]*(?:\.\d+)?", txt):
            nums.add(n.replace(",", ""))
    # the .eml text: decode via the harness-independent email module
    import email, email.policy
    for p in glob.glob(os.path.join(corpus_dir, "**", "*.eml"), recursive=True):
        msg = email.message_from_bytes(open(p, "rb").read(), policy=email.policy.default)
        for part in msg.walk():
            if part.get_content_type() in ("text/plain", "text/html"):
                try:
                    txt = part.get_content()
                except Exception:
                    continue
                for n in re.findall(r"\d[\d,]*(?:\.\d+)?", re.sub(r"<[^>]+>", " ", txt)):
                    nums.add(n.replace(",", ""))
    return nums

def main():
    key_path, audit_path, tag = sys.argv[1:4]
    corpus_dir = sys.argv[sys.argv.index("--corpus-dir") + 1] if "--corpus-dir" in sys.argv else None
    verbose = "--verbose" in sys.argv
    key = json.load(open(key_path))["questions"]
    recs = {}
    for line in open(audit_path, encoding="utf-8"):
        r = json.loads(line)
        if r.get("batch") == tag and "question" in r:
            recs[norm(r["question"])] = r
    known = corpus_numbers(corpus_dir) if corpus_dir else None
    rows, n_pass = [], 0
    cats = {}
    for q in key:
        r = recs.get(norm(q["text"]))
        if not r:
            rows.append((q["n"], "MISSING", q["category"], "no audit line for this question", ""))
            continue
        ans = r.get("answer") or ""
        a = norm(ans)
        refused = bool(r.get("refused")) or is_refusal(ans)
        cited = any(q.get("cite", "") and q["cite"] in (c.get("file") or "") for c in r.get("chunks") or [])
        why = []
        if q["type"] == "refuse":
            bad = [t for t in q.get("must_not") or [] if present(t, a)]
            ok = (refused or ("not" in a and not bad)) and not bad
            if bad: why.append(f"must_not present: {bad}")
            if not refused and not bad: why.append("answered but with no forbidden claim (lenient pass)")
        elif q["type"] == "summary":
            groups = q.get("facts") or []
            hit = [g for g in groups if any(present(t, a) for t in g)]
            need = q.get("min_facts") or max(1, len(groups) // 2)
            bad = [t for t in q.get("must_not") or [] if present(t, a)]
            ok = (not refused) and len(hit) >= need and not bad
            why.append(f"facts {len(hit)}/{len(groups)} (need {need})")
            if refused: why.append("REFUSED a summary question")
            if bad: why.append(f"must_not present: {bad}")
        else:
            miss = [t for t in q.get("must") or [] if not present(t, a)]
            miss_any = [g for g in q.get("any") or [] if not any(present(t, a) for t in g)]
            bad = [t for t in q.get("must_not") or [] if present(t, a)]
            ok = (not refused) and not miss and not miss_any and not bad
            if refused: why.append("REFUSED")
            if miss: why.append(f"missing must: {miss}")
            if miss_any: why.append(f"missing any-group: {miss_any}")
            if bad: why.append(f"must_not present: {bad}")
        fab = []
        if known is not None and not refused:
            for n in re.findall(r"\d[\d,]*(?:\.\d+)?", ans):
                bare = n.replace(",", "")
                if bare not in known and not re.fullmatch(r"\d{1,2}", bare) and bare not in ("2026",):
                    fab.append(n)
        if fab:
            why.append(f"NUMBERS NOT IN CORPUS: {sorted(set(fab))}")
        warns = [w for w in r.get("warnings") or []]
        if warns:
            why.append(f"warnings: {len(warns)}")
        if not cited and q.get("cite"):
            why.append("expected file not cited")
        status = "PASS" if ok else "FAIL"
        n_pass += ok
        c = cats.setdefault(q["category"], [0, 0]); c[1] += 1; c[0] += ok
        rows.append((q["n"], status, q["category"], "; ".join(why), ans if verbose else ans[:160].replace("\n", " ")))
    for n, st, cat, why, ans in rows:
        print(f"Q{n:>2} {st:<7} {cat:<16} {why}")
        if verbose or st != "PASS":
            print(f"      > {ans[:400]}")
    print(f"\nSCORE {n_pass}/{len(key)} = {100.0 * n_pass / len(key):.1f}%")
    for cat, (p, t) in sorted(cats.items()):
        print(f"  {cat:<16} {p}/{t}")
    print(json.dumps({"score": n_pass, "total": len(key), "by_category": cats}))

if __name__ == "__main__":
    main()
