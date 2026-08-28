#!/usr/bin/env python3
"""Generate a needle-in-a-haystack matter for the airlock harness.

Writes matters/<name>/docs/ with many small filler chunks and ONE unique
"needle" fact planted at a chosen depth. Use it to measure how corpus size
and needle depth affect retrieval: does the hybrid search + gate still surface
the one needle chunk as the corpus grows? Each filler paragraph gets its own
heading, so the indexed chunk count stays close to --chunks (no merge).

Synthetic only; no real data. The generated matter is disposable; regenerate
it rather than committing thousands of filler files.

Usage:
  python3 make_haystack.py --chunks 2000 --depth 0.5 --name haystack-2k
  python3 ask.py --matter haystack-2k ingest
  python3 ask.py --matter haystack-2k "What is the Kestrel-9 calibration constant?"
"""
import argparse, os, random

BASE = os.path.dirname(os.path.abspath(__file__))

SUBSYS = ["orbiter", "gimbal", "coolant", "telemetry", "actuator", "regulator",
          "beacon", "manifold", "inverter", "gyroscope", "thruster", "sensor"]
STATUS = ["nominal", "degraded", "standby", "recalibrated", "offline", "peak"]

# The needle uses terms that appear NOWHERE in the filler, so a verbatim
# question is findable by BM25 alone. The paraphrase question shares no keywords
# with the needle, so it stresses the dense (embedder) side only.
NEEDLE = ("The Kestrel-9 calibration constant is 47.3 microvolts, recorded "
          "during the final acceptance run on bench 12.")
NEEDLE_Q_VERBATIM = "What is the Kestrel-9 calibration constant?"
NEEDLE_Q_PARAPHRASE = "What value came out of the last sign-off measurement on bench twelve?"
NEEDLE_ANSWER = "47.3 microvolts"

def filler(i, rng):
    return (f"### Entry {i}\n"
            f"The {rng.choice(SUBSYS)} subsystem reported {rng.choice(STATUS)} "
            f"status at cycle {rng.randint(1000, 9999)}, variance "
            f"{rng.randint(0, 99)}.{rng.randint(0, 9)} units.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=2000, help="number of filler+needle paragraphs")
    ap.add_argument("--depth", type=float, default=0.5, help="needle position, 0.0 (top) to 1.0 (end)")
    ap.add_argument("--name", default="haystack", help="matter name under matters/")
    ap.add_argument("--per-file", type=int, default=250, help="paragraphs per doc file")
    ap.add_argument("--seed", type=int, default=1, help="rng seed, for a reproducible corpus")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    docs = os.path.join(BASE, "matters", a.name, "docs")
    os.makedirs(docs, exist_ok=True)
    needle_at = max(0, min(a.chunks - 1, int(a.chunks * a.depth)))
    paras = []
    for i in range(a.chunks):
        if i == needle_at:
            paras.append("### Acceptance record\n" + NEEDLE)
        else:
            paras.append(filler(i, rng))
    n_files = 0
    for start in range(0, a.chunks, a.per_file):
        block = paras[start:start + a.per_file]
        with open(os.path.join(docs, f"log-{start // a.per_file:04d}.md"), "w", encoding="utf-8") as f:
            f.write("# Synthetic log file (SYNTHETIC TEST DATA)\n\n")
            f.write("\n\n".join(block) + "\n")
        n_files += 1
    with open(os.path.join(BASE, "matters", a.name, "test-questions.txt"), "w", encoding="utf-8") as f:
        f.write(f"# needle at chunk {needle_at}/{a.chunks} (depth {a.depth}); answer = {NEEDLE_ANSWER}\n")
        f.write(NEEDLE_Q_VERBATIM + "\n")
        f.write(NEEDLE_Q_PARAPHRASE + "\n")
    print(f"wrote {a.chunks} paragraphs in {n_files} files -> {docs}")
    print(f"needle at chunk {needle_at} (depth {a.depth}); expected answer = {NEEDLE_ANSWER}")
    print("next:")
    print(f"  python3 ask.py --matter {a.name} ingest")
    print(f'  python3 ask.py --matter {a.name} "{NEEDLE_Q_VERBATIM}"')
    print(f'  python3 ask.py --matter {a.name} "{NEEDLE_Q_PARAPHRASE}"')

if __name__ == "__main__":
    main()
