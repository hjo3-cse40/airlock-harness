#!/usr/bin/env python3
"""Faithfulness eval for the two-stage `summarize` command.

Runs on synthetic-counsel, where every true fact is owned in ANSWER-KEY.md, so
nothing real is involved. Reports DETERMINISTIC signals only and prints each
summary for the eyeball pass. No LLM judge, by design: a second model grading
the first would just add another fallible model.

The key metric is FABRICATED numbers: a number in a summary that appears nowhere
in the matter's full text. That is a real invention. A number that IS in the
full corpus but not in the chunks fed to this run is a COVERAGE gap, not a lie
(it happens only when a big matter is summarized from a diverse subset). Date
fragments like the "11" in 2026-08-11 are in the corpus, so they land in the
coverage bucket, not the fabrication bucket, which is why the split matters.

Usage: python3 eval_summary.py      (needs the chat model loaded in LM Studio;
                                      summarize does not use the embedder)
"""
import re, sys
import ask

MATTER = "synthetic-counsel"
SCOPES = [None, "firm-alpha", "firm-bravo", "firm-charlie"]

def numbers_in(text):
    t = re.sub(r"\[S\d+\]", "", text)
    return set(re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", t))

def scope_text(all_chunks, scope):
    cs = all_chunks if not scope else [c for c in all_chunks if c["file"].startswith(scope)]
    return "\n".join(c["text"] for c in cs).replace(",", "")

def main():
    chat, _emb = ask.server_models()
    if not chat:
        sys.exit("LM Studio server offline: load your chat model, then re-run.")
    all_chunks = ask.load_index(MATTER)["chunks"]
    print(f"model: {chat}\nmatter: {MATTER}\n")

    rows = []
    for scope in SCOPES:
        r = ask.summarize(MATTER, only=scope, quiet=True)
        claims = r["claims"]
        ungrounded = [w for w in r["warnings"] if w.startswith("UNGROUNDED")]
        bad_num = [w for w in r["warnings"] if w.startswith("UNVERIFIED NUMBER")]
        bad_attr = [w for w in r["warnings"] if w.startswith("UNVERIFIED ATTRIBUTION")]
        grounded = len(claims) - len(ungrounded)
        rate = (grounded / len(claims) * 100) if claims else 0.0

        # split flagged numbers: truly absent from the corpus = FABRICATED; present
        # in the corpus but not the fed chunks = coverage gap (not a lie).
        full = scope_text(all_chunks, scope)
        fabricated, coverage = [], []
        for w in bad_num:
            num = w.split(":", 1)[1].strip().replace(",", "")
            (coverage if num in full else fabricated).append(num)

        rows.append((scope, len(claims), grounded, rate, len(fabricated),
                     len(bad_attr), len(coverage)))

        print("=" * 74)
        print(f"SCOPE: {scope or 'WHOLE MATTER'}   ({r['chunks_used']}/{r['chunks_total']} chunks)")
        print("-" * 74)
        print(r["summary"])
        print("-" * 74)
        print(f"claims {len(claims)} | grounded {grounded} ({rate:.0f}%) | "
              f"FABRICATED numbers {len(fabricated)} | attribution errs {len(bad_attr)} | "
              f"ungrounded {len(ungrounded)} | coverage-gap numbers {len(coverage)}")
        if fabricated: print(f"   !! FABRICATED (nowhere in corpus): {sorted(fabricated)}")
        for w in bad_attr + ungrounded:
            print(f"   !! {w}")
        if coverage: print(f"   ~ coverage-gap (real, not in fed subset): {sorted(coverage)}")
        print()

    print("#" * 74)
    print("FAITHFULNESS SCORECARD  (automated; read summaries above for semantic invention)")
    print("#" * 74)
    print(f"{'scope':16}{'claims':>8}{'grounded':>10}{'rate':>7}{'fabr#':>7}{'attr':>6}{'cov-gap':>9}")
    for scope, c, g, rate, fb, ba, cov in rows:
        print(f"{(scope or 'WHOLE'):16}{c:>8}{g:>10}{rate:>6.0f}%{fb:>7}{ba:>6}{cov:>9}")
    tc = sum(x[1] for x in rows); tg = sum(x[2] for x in rows)
    tf = sum(x[4] for x in rows); ta = sum(x[5] for x in rows); tcov = sum(x[6] for x in rows)
    orate = (tg / tc * 100) if tc else 0.0
    print("-" * 63)
    print(f"{'TOTAL':16}{tc:>8}{tg:>10}{orate:>6.0f}%{tf:>7}{ta:>6}{tcov:>9}")
    print()
    print("Targets: grounding 100%, FABRICATED 0, attribution 0. cov-gap > 0 only means")
    print("a big matter was summarized from a subset (real facts, just not all fed).")
    print("A deterministic check cannot catch a dropped condition or added qualifier, so")
    print("the eyeball pass over the summaries above is part of the eval, not optional.")

if __name__ == "__main__":
    main()
