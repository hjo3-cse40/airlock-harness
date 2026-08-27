# Strata-Airlock

An air-gapped, cite-or-refuse Q&A harness for sensitive documents, running
entirely on local language models. No cloud, no telemetry, no network calls.

## The problem

Small local models fail silently. When retrieval is weak, when context is
truncated, or when the model simply does not know, the output is still fluent
and confident. The user gets a wrong answer and no error signal.

Strata-Airlock is built around one contract: **cite a source or refuse.**
When the system cannot ground an answer, it goes silent instead of guessing.

## How it works

Each question runs through a fixed pipeline:

1. **Hybrid retrieval.** BM25 plus a small dense embedder, fused with
   reciprocal rank fusion. Falls back gracefully to BM25-only when no
   embedding model is loaded.
2. **Refusal gate.** If neither retrieval signal clears its threshold, the
   harness refuses before the model is ever called.
3. **Grounded generation.** The model answers from numbered source chunks
   via any OpenAI-compatible local server (built against LM Studio).
4. **Deterministic checks.** Any number in the answer that does not appear
   in a cited source is flagged `UNVERIFIED NUMBER`. No LLM judges.
5. **Audit log.** Every question, score, refusal, and token count is
   appended to a JSONL audit trail.

## Design principles

- **Stdlib only.** Zero pip installs. One Python file you can read.
- **Jobs, not chat.** One question, one retrieval, one model call.
- **Refusals are measured.** A refusal rate means nothing without the
  false-refusal rate next to it.
- **Coverage is checked.** A file that never got indexed is a silent
  failure too. `coverage` diffs the document folder against the index
  and warns loudly.
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

    strata/
    ├── ask.py                 # the entire harness
    ├── prompt.txt             # grounding rules for the model
    └── matters/
        ├── fixtures/          # selftest corpus
        └── example-matter/
            ├── docs/
            │   ├── alpha/     # one folder per source, scopable via --only
            │   ├── bravo/
            │   └── collateral/  # reference material, kept out of scoped asks
            ├── index.json     # chunk index built by ingest
            └── audit.jsonl    # append-only log of every question and refusal

## Usage

    python ask.py selftest
    python ask.py --matter <name> ingest
    python ask.py --matter <name> coverage
    python ask.py --matter <name> "your question"
    python ask.py --matter <name> batch questions.txt

Useful flags: `--only <folder>` to scope retrieval, `--top-k`,
`--min-score` (BM25 gate), `--dense-min` (cosine gate).

## Status

v0. Active development. The design document lives in this repo; the
harness code lands here as it stabilizes.
