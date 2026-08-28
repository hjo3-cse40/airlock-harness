# Airlock

An air-gapped, cite-or-refuse Q&A harness for sensitive documents, running
entirely on local language models. No cloud, no telemetry, no network calls.

## The problem

Small local models fail silently. When retrieval is weak, when context is
truncated, or when the model simply does not know, the output is still fluent
and confident. The user gets a wrong answer and no error signal.

Airlock is built around one contract: **cite a source or refuse.**
When the system cannot ground an answer, it goes silent instead of guessing.

## How it works

Each question runs through a fixed pipeline:

1. **Hybrid retrieval.** BM25 plus a small dense embedder, fused with
   reciprocal rank fusion. Falls back gracefully to BM25-only when no
   embedding model is loaded. `--diverse` takes the best chunk per source
   before filling slots, so questions that span several sources do not lose a
   source to another source's chunks.
2. **Refusal gate.** If neither retrieval signal clears its threshold, the
   harness refuses before the model is ever called.
3. **Grounded generation.** The model answers from numbered source chunks
   via any OpenAI-compatible local server (built against LM Studio). Decoding
   is greedy (temperature 0), so identical questions give identical answers
   and the audit trail is reproducible.
4. **Deterministic checks.** Any number in the answer that is not in a cited
   source is flagged `UNVERIFIED NUMBER`. Any claim that attributes a
   statement to a party who is only a recipient of the cited sources, not a
   sender or the author, is flagged `UNVERIFIED ATTRIBUTION`. Dumb code, no
   LLM judges.
5. **Audit log.** Every question, score, refusal, warning, and token count is
   appended to a per-machine JSONL audit trail, so two machines that share a
   matter never conflict.

## Design principles

- **Stdlib only.** Zero pip installs. One Python file you can read.
- **Jobs, not chat.** One question, one retrieval, one model call.
- **Refusals are measured.** A refusal rate means nothing without the
  false-refusal rate next to it.
- **Coverage is checked.** A file that never got indexed is a silent
  failure too. `coverage` diffs the document folder against the index
  and warns loudly.
- **Reproducible by default.** Greedy decoding means a benchmark run can be
  rerun and compared without sampling noise.
- **No real data in this repo. Ever.** Only synthetic corpora and results
  computed on synthetic corpora are published here.

## Benchmark

On a synthetic 40-question benchmark with fully known ground truth,
accuracy improved from 45% to ~90% across six harness iterations, with
zero fabricated numbers and zero wrong citations in every run. Under
overload, the system degrades to silence. It does not lie.

## Layout

Documents are organized into isolated "matters". Nothing crosses a
matter boundary: not retrieval, not the index, not the audit log.

    airlock/
    ├── ask.py                 # the entire harness
    ├── prompt.txt             # grounding rules for the model
    ├── make_haystack.py       # generate a needle-in-a-haystack test corpus
    └── matters/
        ├── fixtures/          # selftest corpus
        └── example-matter/
            ├── docs/
            │   ├── alpha/     # one folder per source, scopable via --only
            │   ├── bravo/
            │   └── collateral/  # reference material, kept out of scoped asks
            ├── index.json     # chunk index built by ingest
            ├── results/       # per-run experiment notes
            └── audit/
                └── <machine>.jsonl  # per-machine append-only log

## Usage

    python ask.py selftest
    python ask.py --matter <name> ingest
    python ask.py --matter <name> coverage
    python ask.py --matter <name> "your question"
    python ask.py --matter <name> batch questions.txt
    python ask.py --matter <name> chat

`chat` is an interactive prompt: one grounded, audited answer per line, with
session settings held between lines. Backslash commands change those settings
(`\show`, `\set`, `\only`, `\diverse`, `\help`, `\exit`).

Documents are read from `.md`, `.txt`, and `.pptx` natively. Other formats
(`.pdf`, `.docx`, ...) are indexed only when a same-stem `.txt` sits beside
them, and `coverage` warns about any file left out.

Useful flags: `--only <folder>` to scope retrieval, `--top-k`,
`--min-score` (BM25 gate), `--dense-min` (cosine gate), `--diverse`
(one best chunk per source, then fill; pair with a larger `--top-k` for
questions that span many sources). In `batch` and `chat`, prefix a single
line with `<flags> ::` to override those flags for that line only.

## Status

v0. Active development. Greedy decoding, source-diverse retrieval, an
interactive `chat` REPL, and an attribution check have landed. Test tooling
includes a needle-in-a-haystack corpus generator and a prompt-injection
probe; hardening the model against document-borne instructions is an open
item. Per-run experiment notes live under each matter's `results/`. The
harness code lands here as it stabilizes.
