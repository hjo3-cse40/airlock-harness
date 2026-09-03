# Airlock

An air-gapped, cite-or-refuse Q&A and summarization harness for sensitive
documents, running entirely on local language models. No cloud, no telemetry,
no network calls.

## The problem

Small local models fail silently. When retrieval is weak, when context is
truncated, or when the model simply does not know, the output is still fluent
and confident. The user gets a wrong answer and no error signal.

Airlock is built around one contract: **cite a source or refuse.** When the
system cannot ground an answer, it goes silent instead of guessing.

## Two modes

- **Ask (extract).** One question, one retrieval, one grounded answer, or a
  refusal. This is the validated core.
- **Summarize (compose).** A two-stage summary: first gather the matter's own
  chunks as numbered, cited sources, then compose bullets from only those. Every
  bullet carries a citation, and the same deterministic checks run over the
  result. Summarizing is a separate, clearly lower-trust mode, because composed
  prose can still drop a condition or add a qualifier that no check catches.

## How it works

Each question runs through a fixed pipeline:

1. **Hybrid retrieval.** BM25 plus a small dense embedder, fused with
   reciprocal rank fusion. Falls back to BM25-only when no embedding model is
   loaded. `--diverse` takes the best chunk per source before filling slots.
2. **Refusal gate.** If neither retrieval signal clears its threshold, the
   harness refuses before the model is ever called.
3. **Grounded generation.** The model answers from numbered source chunks via
   any OpenAI-compatible local server (built against LM Studio). Decoding is
   greedy (temperature 0), so identical inputs give identical outputs and the
   audit trail is reproducible.
4. **Deterministic checks.** A number not in a cited source is flagged
   `UNVERIFIED NUMBER`. A statement attributed to a party who is only a
   recipient of the cited sources is flagged `UNVERIFIED ATTRIBUTION`. In a
   summary, a bullet with no citation is flagged `UNGROUNDED SENTENCE`. Dumb
   code, no LLM judges.
5. **Audit log.** Every question, score, refusal, warning, and token count is
   appended to a per-machine JSONL trail, so two machines that share a matter
   never conflict.

## Design principles

- **Stdlib only.** Zero pip installs. One Python file you can read.
- **Jobs, not chat.** One question, one retrieval, one model call.
- **Refusals are measured.** A refusal rate means nothing without the
  false-refusal rate next to it.
- **Coverage is checked.** A file that never got indexed is a silent failure.
  `coverage` diffs the document folder against the index and warns loudly, and
  ingest converts what it can with local tools before it indexes.
- **Reproducible by default.** Greedy decoding lets a run be rerun and compared
  without sampling noise.
- **No real data in this repo. Ever.** Only synthetic corpora and synthetic
  results are published here.

## Benchmarks

- **Extraction.** On a synthetic 40-question set with known ground truth,
  accuracy improved from 45% to ~98% across harness iterations, with zero
  fabricated numbers and zero wrong citations in every run. Under overload the
  system degrades to silence, not to lies.
- **Summarization.** A separate faithfulness eval scores each summary for
  grounding rate, fabricated numbers (found nowhere in the corpus), and
  attribution errors. Across four scopes: 98 cited claims, 100% grounded, zero
  fabricated, zero attribution errors, and byte-identical across temp-0 runs.

## Layout

Documents are organized into isolated "matters". Nothing crosses a matter
boundary: not retrieval, not the index, not the audit log.

    airlock/
    ├── ask.py                 # the entire harness
    ├── prompt.txt             # grounding rules for the model
    ├── eval_summary.py        # faithfulness eval for the summarize mode
    ├── make_haystack.py       # generate a needle-in-a-haystack test corpus
    ├── make_fixture_docs.py   # build the .docx/.eml fixtures and the format probe
    └── matters/
        ├── fixtures/          # selftest corpus
        └── example-matter/
            ├── docs/
            │   ├── alpha/     # one folder per source, scopable via --only
            │   ├── bravo/
            │   ├── collateral/  # reference material, kept out of scoped asks
            │   └── .derived.json  # sidecars made by ingest, and from what
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
    python ask.py --matter <name> summarize [--only <folder>] [--out file.md]

`chat` is an interactive prompt: one grounded, audited answer per line, with
session settings held between lines (`\show`, `\set`, `\only`, `\diverse`,
`\help`, `\exit`).

`summarize` gathers a matter (or one scoped folder) into cited bullets. A whole
deck or correspondence set fits in a single pass; a larger matter is summarized
from a diverse subset and the coverage gap is reported, never hidden.

## Document formats

| Format | How it is read |
|---|---|
| `.md` `.txt` | natively; pdftotext form feeds become `page N` labels |
| `.pptx` | natively; one section per slide, `slide N`, shapes read in column order |
| `.docx` | natively; Heading styles become chunk headings, tables stay whole |
| `.eml` | natively; heading is `date From -> To`, attachments are listed, not extracted |
| `.pdf` | converted at ingest with `pdftotext -layout` into a same-stem `.txt` |
| `.doc` `.rtf` `.html` | converted at ingest with `textutil` into a same-stem `.docx` |
| `.ppt` | converted at ingest with LibreOffice `soffice` into a same-stem `.pptx` |
| `.msg` `.pages` `.key` `.xlsx` | not read; export by hand (coverage says how) |
| images, scanned PDFs | not read; no local OCR pass yet |

Conversion uses local command-line tools only, so nothing leaves the machine.
A missing tool leaves the file skipped and `coverage` names the tool. A
converted sidecar is tracked in `docs/.derived.json` and remade when its source
changes; a companion file a person made is never overwritten, only flagged as
stale when the source is newer. A conversion that yields no text is treated as
a scan and reported, not indexed. `coverage` warns about any file left out.
The synthetic `matters/format-probe/` holds one file per format with a
question set, so the whole path is exercised end to end.

Useful flags: `--only <folder>`, `--top-k`, `--min-score` (BM25 gate),
`--dense-min` (cosine gate), `--diverse`. In `batch` and `chat`, prefix a line
with `<flags> ::` to override for that line only.

## Status

v0, active development. Greedy decoding, source-diverse retrieval, an
interactive `chat` REPL, an attribution check, and a two-stage `summarize` mode
with a grounding check have landed. Sources are walled off as untrusted text, so
planted instructions inside a document are ignored, not obeyed. selftest runs 59
checks. Test tooling includes a needle-in-a-haystack generator, a
prompt-injection probe, a refusal-precision probe, and the summarization
faithfulness eval. Per-run notes live under each matter's `results/`.
