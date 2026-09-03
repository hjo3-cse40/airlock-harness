# Airlock

An air-gapped, cite-or-refuse Q&A and summarization harness for sensitive
documents, running entirely on local language models. No cloud, no telemetry,
no network calls. One Python file, standard library only.

## The problem

Small local models fail silently. When retrieval is weak, when context is
truncated, or when the model simply does not know, the output is still fluent
and confident. The user gets a wrong answer and no error signal.

Airlock is built around one contract: **cite a source or refuse.** When the
system cannot ground an answer, it goes silent instead of guessing.

## Quick start

1. Run a local OpenAI-compatible server (built against LM Studio) on
   `127.0.0.1:1234` with a chat model loaded. An embedding model is optional;
   without one, retrieval is BM25-only.
2. Put documents under `matters/<name>/docs/`, one subfolder per source.
3. Build the index, then chat:

```
python3 ask.py selftest
python3 ask.py --matter <name> ingest
python3 ask.py --matter <name> chat
```

A synthetic matter ships with the repo, so the whole path can be tried without
any real documents:

```
python3 ask.py --matter synthetic-counsel ingest
python3 ask.py --matter synthetic-counsel chat
```

## Chat

`chat` is an interactive prompt. Every line is either a question or a `/`
command. A question runs one grounded, audited answer. A command changes the
session for the lines that follow. The prompt shows where you are:

```
synthetic-counsel >               answers come from the whole matter
synthetic-counsel/firm-alpha >    answers come only from that folder
```

Type `/` and a menu opens above the prompt with every command. Keep typing to
filter it. The highlighted row is black on an orange band, command names are
cyan, and help text is dimmed, so the menu stands apart from the transcript.
Set the standard `NO_COLOR` variable to fall back to reverse video. Keys:

| Key | Menu open | Menu closed |
|---|---|---|
| up / down | move the highlight | move between the lines of a multi-line question, then walk the history (up recalls the last line) |
| option-enter | | insert a newline (shift-enter cannot: the terminal sends it as enter) |
| shift + left / right, shift + option + arrows, shift + home / end | | select characters, words, or to the line ends; typing replaces the selection, backspace deletes it |
| option-a, option-c | | select all, copy the selection (the whole line when nothing is selected) |
| option + left / right, ctrl + left / right | | jump a word |
| tab | fill the highlighted row | |
| enter | run the highlighted row | send the line |
| esc | close the menu | |
| ctrl-a / ctrl-e, home / end | | start / end of line |
| ctrl-u, ctrl-k, ctrl-w | | kill the line, to the end, the previous word |
| ctrl-c | | drop the line and start over |
| ctrl-d | | leave (on an empty line) |

Commands:

| Command | Effect |
|---|---|
| `/scope <folder>` | answer only from that folder (the menu lists the folders) |
| `/scope` | back to the whole matter |
| `/folders` | list the folders under `docs/`, with indexed, skipped and new counts |
| `/matter <name>` | switch to another matter, reload its index, clear the scope |
| `/matters` | list the matters |
| `/reingest` | convert new files, rebuild the index, show coverage |
| `/reason <question>` | think first, then compute and compare over the sources; conclusions are labeled `[INFERENCE]` (slower, lower trust) |
| `/think [on\|off]` | show the `/reason` thinking trace in gray as it streams; no value toggles (default off, a counter shows instead) |
| `/set <key> <value>` | `top-k`, `min-score` (BM25 gate), `dense-min` (cosine gate), `think-budget` (reason-mode `max_tokens`, default 8000) |
| `/diverse [on\|off]` | best chunk per source first; no value toggles |
| `/show` | print the current settings |
| `/help` | list the commands |
| `/exit` | leave |

Each turn is easy to find in the scrollback: the question you typed becomes a
teal band with the mode (`ask`, `reason`, `summarize`) and the scope, a cyan
`answer` rule shows where the answer starts and carries a context estimate
("about 1,500 tokens in, 4% of 32k"), the sources list is dim, and warning
lines are yellow (a check fired) or red (no usable answer). The exact token
count follows the sources. `NO_COLOR` turns all of this into plain text.

One line can override the session without changing it: prefix the question
with `--only <folder> --top-k N --diverse ::`. The same prefix works in a
`batch` questions file.

History persists per matter in `matters/<name>/audit/chat-history.txt`,
beside the audit log and inside the same privacy boundary. When the input is
not a terminal (a pipe, a test), the chat falls back to a plain prompt.

## Three modes

- **Ask (extract).** One question, one retrieval, one grounded answer, or a
  refusal. This is the validated core. The model does not think first: every
  extraction call sends `reasoning_effort: "none"`, so a thinking toggle left
  on in the LM Studio UI cannot change a grounded run.
- **Reason (think, compute, compare).** The same retrieval and gate, a
  different contract with the model (`reason-prompt.txt`): it may add, compare
  and conclude over the cited facts, it must show the arithmetic, and every
  conclusion that is not written in a source carries an `[INFERENCE]` label.
  The model thinks before it answers; the thinking trace and the token count
  go into the audit line, and a live counter shows progress (`/think on` or
  `--show-thinking` streams the trace itself in gray instead). It retrieves at
  least 8 chunks, best chunk per source first. Expect one to three minutes per
  question on a 9B model, against a few seconds for ask. Lower trust than ask:
  a computed number is a new number, so the number check reports it and the
  reader checks the arithmetic. Reason answers are sampled (temperature 0.6,
  the setting Qwen recommends for thinking) because greedy decoding can lock
  the trace into a verbatim cycle, so they are not byte-reproducible; the
  audit line keeps the trace. If the trace does start repeating itself the
  run is stopped and says `LOOP`; if the thinking eats the whole budget the
  run says `TRUNCATED` instead of pretending; raise the budget with
  `/set think-budget 12000` (the thinking and the answer share it).
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

## All commands

```
python3 ask.py selftest
python3 ask.py --matter <name> ingest
python3 ask.py --matter <name> coverage
python3 ask.py --matter <name> chat
python3 ask.py --matter <name> "your question"
python3 ask.py --matter <name> reason "a question that needs arithmetic or comparison" [--show-thinking] [--think-budget N]
python3 ask.py --matter <name> batch questions.txt
python3 ask.py --matter <name> summarize [--only <folder>] [--out file.md]
```

Flags: `--only <folder>`, `--top-k`, `--min-score` (BM25 gate), `--dense-min`
(cosine gate), `--diverse`.

`summarize` gathers a matter (or one scoped folder) into cited bullets. A whole
deck or correspondence set fits in a single pass; a larger matter is summarized
from a diverse subset and the coverage gap is reported, never hidden.

## Design principles

- **Stdlib only.** Zero pip installs. One Python file you can read. The chat
  editor, the Office parsers, and the email parser are all standard library.
- **Jobs, not chat.** One question, one retrieval, one model call. The chat
  prompt is a loop over that job; no answer carries into the next turn.
- **Refusals are measured.** A refusal rate means nothing without the
  false-refusal rate next to it.
- **Coverage is checked.** A file that never got indexed is a silent failure.
  `coverage` diffs the document folder against the index and warns loudly, and
  ingest converts what it can with local tools before it indexes.
- **Reproducible by default.** Greedy decoding lets a run be rerun and compared
  without sampling noise.
- **No real data in this repo. Ever.** Only synthetic corpora and synthetic
  results are published here.

## Layout

Documents are organized into isolated "matters". Nothing crosses a matter
boundary: not retrieval, not the index, not the audit log, not the history.

    airlock/
    ├── ask.py                 # the entire harness
    ├── prompt.txt             # grounding rules for the model (ask, extraction)
    ├── reason-prompt.txt      # rules for reason mode (compute, label inferences)
    ├── eval_summary.py        # faithfulness eval for the summarize mode
    ├── make_haystack.py       # generate a needle-in-a-haystack test corpus
    ├── make_fixture_docs.py   # build the .docx/.eml fixtures and the format probe
    └── matters/
        ├── fixtures/          # selftest corpus
        ├── synthetic-counsel/ # synthetic benchmark matter with an answer key
        ├── format-probe/      # one synthetic file per document format
        └── example-matter/
            ├── docs/
            │   ├── alpha/     # one folder per source, scopable via /scope
            │   ├── bravo/
            │   ├── collateral/  # reference material, kept out of scoped asks
            │   └── .derived.json  # sidecars made by ingest, and from what
            ├── index.json     # chunk index built by ingest
            ├── results/       # per-run experiment notes
            └── audit/
                ├── <machine>.jsonl   # per-machine append-only log
                └── chat-history.txt  # chat history for this matter

## Testing

- `python3 ask.py selftest` runs the deterministic checks: chunking, retrieval,
  the refusal gate, the number and attribution checks, the document parsers,
  coverage and conversion rules, the chat dispatcher, the menu, the line
  editor driven by injected keys, and the reason-mode request shape. No terminal or model is needed; when a server
  is up, one live question runs at the end.
- `matters/synthetic-counsel/test-questions.txt` is a 40-question benchmark
  with `ANSWER-KEY.md`. Run it with `batch` and score by hand against the key.
- `matters/format-probe/test-questions.txt` asks one question per document
  format, with its own answer key, and one trap that must be refused.
- Test tooling also includes a needle-in-a-haystack generator, a
  prompt-injection probe, a refusal-precision probe, and the summarization
  faithfulness eval (`eval_summary.py`).

## Benchmarks

- **Extraction.** On the synthetic 40-question set with known ground truth,
  accuracy improved from 45% to ~98% across harness iterations, with zero
  fabricated numbers and zero wrong citations in every run. Under overload the
  system degrades to silence, not to lies.
- **Summarization.** A separate faithfulness eval scores each summary for
  grounding rate, fabricated numbers (found nowhere in the corpus), and
  attribution errors. Across four scopes: 98 cited claims, 100% grounded, zero
  fabricated, zero attribution errors, and byte-identical across temp-0 runs.

## Status

v0, active development. Greedy decoding, source-diverse retrieval, a chat
prompt with slash commands and folder scoping, native Word and email parsing
with local-tool conversion for the rest, an attribution check, and a two-stage
`summarize` mode with a grounding check have landed. Sources are walled off as
untrusted text, so planted instructions inside a document are ignored, not
obeyed. Per-run notes live under each matter's `results/`.
