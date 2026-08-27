#!/usr/bin/env python3
"""strata-v0: local cite-or-refuse Q&A over a folder of documents.

Zero dependencies (Python 3 stdlib only). The only network call is to
LM Studio on 127.0.0.1:1234. Nothing leaves the machine.

Usage:
  python3 ask.py selftest
  python3 ask.py --matter patent-slw ingest
  python3 ask.py --matter patent-slw "What fee did the firm quote?"
  python3 ask.py --matter synthetic-counsel batch test-questions.txt
"""
import argparse, hashlib, json, math, os, re, sys, time, urllib.request, urllib.error
import zipfile, tempfile, xml.etree.ElementTree as ET

BASE = os.path.dirname(os.path.abspath(__file__))
SERVER = "http://127.0.0.1:1234/v1"
DOC_EXTS = (".md", ".markdown", ".txt")
PPTX_EXTS = (".pptx",)
INGEST_EXTS = DOC_EXTS + PPTX_EXTS
# Formats we deliberately do NOT parse. A file with one of these extensions is
# "covered" only when a same-stem .txt sits beside it (the pdftotext workflow).
CONVERTIBLE_EXTS = (".pdf", ".doc", ".docx", ".ppt", ".eml", ".msg", ".rtf",
                    ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".heic")

# ---------------- tokenize ----------------

STOP = set("the a an of to in for and or is are was were be on at as by with that this it from".split())

def _norm(t):
    # light plural stemming: fees->fee, applications->application; both sides
    # of the match get the same transform, so consistency is what matters
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t

def tokenize(text):
    out = []
    for t in re.findall(r"[a-z0-9]+(?:[._\-][a-z0-9]+)*", text.lower()):
        if t in STOP:
            continue
        out.append(_norm(t))
        if re.search(r"[._\-]", t):  # compound like zilka-kotab: also match its parts
            out.extend(_norm(p) for p in re.split(r"[._\-]+", t) if p and p not in STOP)
    return out

# ---------------- chunking ----------------

CHUNK_VERSION = 4  # bump when chunking/embedding logic changes, forces re-index

# ---------------- pptx ----------------

_NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main",
       "p": "http://schemas.openxmlformats.org/presentationml/2006/main"}

def _a_text(node):
    """Text of one drawingml shape: paragraphs preserved, <a:br/> as newline."""
    lines = []
    for para in node.iterfind(".//a:p", _NS):
        buf = []
        for el in para.iter():
            tag = el.tag.split("}")[-1]
            if tag == "t" and el.text:
                buf.append(el.text)
            elif tag == "br":
                buf.append("\n")
        line = "".join(buf).strip()
        if line:
            lines.append(line)
    return lines

def _a_table(frame):
    """A pptx table -> markdown rows, so the chunker keeps it whole."""
    rows = []
    for tr in frame.iterfind(".//a:tbl/a:tr", _NS):
        cells = []
        for tc in tr.iterfind("a:tc", _NS):
            cells.append(" ".join(_a_text(tc)).replace("|", "/"))
        if any(c.strip() for c in cells):
            rows.append("| " + " | ".join(cells) + " |")
    return rows

def _shape_box(sp):
    """(y, x, cx) in EMU, or None when the shape inherits from its layout."""
    for path_ in ("./p:spPr/a:xfrm", "./p:xfrm", "./p:grpSpPr/a:xfrm"):
        xf = sp.find(path_, _NS)
        if xf is None:
            continue
        off, ext = xf.find("a:off", _NS), xf.find("a:ext", _NS)
        if off is None:
            continue
        try:
            return (int(off.get("y", 0)), int(off.get("x", 0)),
                    int(ext.get("cx", 0)) if ext is not None else 0)
        except ValueError:
            return None
    return None

def _walk_shapes(tree, base=(0, 0), depth=0):
    """Yield (y, x, cx, seq, lines) per shape, recursing into groups."""
    for seq, sp in enumerate(list(tree)):
        tag = sp.tag.split("}")[-1]
        if tag not in ("sp", "graphicFrame", "grpSp", "pic"):
            continue
        box = _shape_box(sp)
        y, x = (base[0] + box[0], base[1] + box[1]) if box else (base[0], base[1])
        if tag == "grpSp":
            yield from _walk_shapes(sp, (y, x), depth + 1)
            continue
        lines = _a_table(sp) if sp.find(".//a:tbl", _NS) is not None else _a_text(sp)
        if lines:
            yield (y if box else 10 ** 12 + seq, x, box[2] if box else 0, seq, lines)

def _slide_lines(xml_bytes, slide_w=12192000):
    """Slide XML -> text lines grouped the way a reader would take them.

    XML order is authoring order, not visual order, so a grid layout silently
    scrambles which label belongs to which value. Two cases:
      * multi-column grid  -> read COLUMN-major, so each column's label, value
        and caption stay together and land in the same chunk
      * anything else      -> read top to bottom, left to right
    Full-width shapes (title, subtitle, footer) are banners and come first.
    Groups are separated by a blank line, which is where the chunker splits.
    """
    root = ET.fromstring(xml_bytes)
    tree = root.find(".//p:cSld/p:spTree", _NS)
    if tree is None:
        return []
    shapes = list(_walk_shapes(tree))
    if not shapes:
        return []
    BAND = 320000                      # EMU, ~0.35in vertical tolerance
    XTOL = max(slide_w // 12, 1)       # column tolerance
    banners = [t for t in shapes if t[2] >= 0.6 * slide_w]
    grid = [t for t in shapes if t[2] < 0.6 * slide_w]
    groups = []
    if banners:
        banners.sort(key=lambda t: (t[0], t[1]))
        groups.append([l for t in banners for l in t[4]])
    # cluster by x on GAPS, not on rounding: a box nudged off its column centre
    # must not fall into the neighbouring band (that orphans it from its label)
    cols, cur, prev = [], [], None
    for t in sorted(grid, key=lambda t: t[1]):
        if prev is not None and t[1] - prev > XTOL:
            cols.append(cur); cur = []
        cur.append(t); prev = t[1]
    if cur:
        cols.append(cur)
    is_grid = len(cols) >= 2 and max(len(c) for c in cols) >= 2
    if is_grid:
        for col in cols:
            col = sorted(col, key=lambda t: (t[0], t[3]))
            groups.append([l for t in col for l in t[4]])
    else:
        grid.sort(key=lambda t: (round(t[0] / BAND), t[1], t[3]))
        for t in grid:
            groups.append(list(t[4]))
    out = []
    for g in groups:
        if any(l.strip() for l in g):
            out.extend(g)
            out.append("")
    return out

def pptx_slides(path):
    """[(slide_no, [lines])] plus the count of embedded images."""
    slides, images = [], 0
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        images = sum(1 for n in names if n.startswith("ppt/media/"))
        slide_w = 12192000
        if "ppt/presentation.xml" in names:
            sz = ET.fromstring(z.read("ppt/presentation.xml")).find("p:sldSz", _NS)
            if sz is not None and sz.get("cx"):
                slide_w = int(sz.get("cx"))
        def num(n):
            m = re.search(r"(\d+)\.xml$", n)
            return int(m.group(1)) if m else 0
        sl = sorted([n for n in names
                     if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)], key=num)
        for n in sl:
            no = num(n)
            lines = _slide_lines(z.read(n), slide_w)
            note = "ppt/notesSlides/notesSlide%d.xml" % no
            if note in names:
                nl = [l for l in _slide_lines(z.read(note), slide_w)
                      if l.strip() != str(no)]
                if any(l.strip() for l in nl):
                    lines += ["", "Speaker notes:"] + nl
            slides.append((no, lines))
    return slides, images

def chunk_pptx(path, rel):
    chunks = []
    slides, _ = pptx_slides(path)
    for no, lines in slides:
        chunks.extend(_chunk_lines(lines, rel, f"slide {no}"))
    return _merge_and_id(chunks, rel)

def chunk_file(path, rel):
    """Split a file into chunks at headings and blank lines.
    A markdown table stays one chunk. Never split inside a line.
    pdftotext output uses form feeds as page breaks: label chunks 'page N'.
    .pptx is read natively: one section per slide, labelled 'slide N'."""
    if path.lower().endswith(PPTX_EXTS):
        return chunk_pptx(path, rel)
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if "\f" in text:
        chunks = []
        for pno, page in enumerate(text.split("\f"), 1):
            chunks.extend(_chunk_lines(page.splitlines(), rel, f"page {pno}"))
    else:
        chunks = _chunk_lines(text.splitlines(), rel, "")
    return _merge_and_id(chunks, rel)

def _chunk_lines(lines, rel, base_heading):
    chunks, buf, heading, in_table = [], [], base_heading, False

    def flush():
        text = "\n".join(buf).strip()
        if text:
            chunks.append({"file": rel, "heading": heading, "text": text})
        buf.clear()

    for line in lines:
        is_table = line.lstrip().startswith("|")
        if re.match(r"^#{1,6} ", line):
            flush()
            h = line.lstrip("#").strip()
            heading = f"{base_heading} / {h}" if base_heading else h
            in_table = False
            continue
        if is_table and not in_table:          # table starts: own chunk
            flush()
            in_table = True
        elif not is_table and in_table:        # table ends
            flush()
            in_table = False
        if not line.strip() and not in_table:  # blank line = paragraph break
            flush()
            continue
        buf.append(line)
    flush()
    return chunks

def _merge_and_id(chunks, rel):
    # merge tiny neighbor chunks under the same heading
    merged = []
    for c in chunks:
        if merged and merged[-1]["heading"] == c["heading"] \
           and len(merged[-1]["text"]) + len(c["text"]) < 900 \
           and not c["text"].lstrip().startswith("|") \
           and not merged[-1]["text"].lstrip().startswith("|"):
            merged[-1]["text"] += "\n\n" + c["text"]
        else:
            merged.append(c)
    for i, c in enumerate(merged):
        c["id"] = f"{rel}#{i}"
    return merged

# ---------------- index ----------------

def matter_dir(matter):
    d = os.path.join(BASE, "matters", matter)
    if not os.path.isdir(os.path.join(d, "docs")):
        sys.exit(f"No such matter: {matter} (expected {d}/docs/)")
    return d

def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def scan_coverage(docs):
    """Classify every file under docs/. Returns (indexable, skipped).

    A file is 'covered by companion' when a same-stem .txt sits beside it,
    which is the pdftotext workflow. Anything else unreadable is SKIPPED, and
    a skipped file is invisible at query time unless we say so out loud.
    """
    indexable, skipped = {}, []
    by_stem = {}
    for root, _, names in os.walk(docs):
        for name in names:
            stem = os.path.splitext(name)[0].lower()
            by_stem.setdefault((root, stem), set()).add(os.path.splitext(name)[1].lower())
    for root, _, names in os.walk(docs):
        for name in sorted(names):
            if name.startswith("."):
                continue
            p_ = os.path.join(root, name)
            rel = os.path.relpath(p_, docs)
            ext = os.path.splitext(name)[1].lower()
            if ext in INGEST_EXTS:
                indexable[rel] = file_hash(p_)
                continue
            stem = os.path.splitext(name)[0].lower()
            companions = by_stem.get((root, stem), set())
            if any(c in DOC_EXTS for c in companions):
                continue  # e.g. foo.pdf next to foo.txt
            why = ("convert it first (pdftotext -layout / export to .txt)"
                   if ext in CONVERTIBLE_EXTS else "unsupported file type")
            skipped.append({"file": rel, "ext": ext, "why": why})
    return indexable, skipped

def _warn_skipped(skipped, docs):
    if not skipped:
        return
    print("", file=sys.stderr)
    print("!" * 72, file=sys.stderr)
    print(f"COVERAGE WARNING: {len(skipped)} file(s) in {docs} are NOT indexed.",
          file=sys.stderr)
    print("Questions cannot see them. An answer may look complete and be wrong.",
          file=sys.stderr)
    for sk in skipped:
        print(f"  - {sk['file']}  ({sk['why']})", file=sys.stderr)
    print("!" * 72, file=sys.stderr)
    print("", file=sys.stderr)

def coverage(matter):
    d = matter_dir(matter)
    docs = os.path.join(d, "docs")
    indexable, skipped = scan_coverage(docs)
    idx_path = os.path.join(d, "index.json")
    indexed = set()
    if os.path.exists(idx_path):
        with open(idx_path, encoding="utf-8") as f:
            indexed = set(json.load(f).get("files", {}))
    print(f"matter: {matter}")
    print(f"  indexable files : {len(indexable)}")
    print(f"  in current index: {len(indexed)}")
    stale = sorted(set(indexable) - indexed)
    if stale:
        print(f"  NOT YET INDEXED : {len(stale)} (run ingest)")
        for r in stale:
            print(f"    - {r}")
    gone = sorted(indexed - set(indexable))
    if gone:
        print(f"  in index but gone from docs/: {len(gone)}")
        for r in gone:
            print(f"    - {r}")
    _warn_skipped(skipped, docs)
    if not skipped and not stale and not gone:
        print("  OK: every file under docs/ is represented in the index.")
    return 1 if (skipped or stale or gone) else 0

def ingest(matter, quiet=False):
    d = matter_dir(matter)
    docs = os.path.join(d, "docs")
    index_path = os.path.join(d, "index.json")
    old = {}
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            old = json.load(f)
    files, skipped = scan_coverage(docs)
    if not quiet:
        _warn_skipped(skipped, docs)
    if not files:
        sys.exit(f"No .md/.txt/.pptx files in {docs}")
    _, emb = server_models()
    if files == old.get("files") and old.get("chunk_version") == CHUNK_VERSION \
            and (old.get("embed_model") or not emb):
        if not quiet:
            print(f"Index up to date ({len(old.get('chunks', []))} chunks, {len(files)} files).")
        old["skipped"] = skipped
        return old
    chunks = []
    for rel in sorted(files):
        chunks.extend(chunk_file(os.path.join(docs, rel), rel))
    if emb:
        vecs = embed_texts([c["heading"] + "\n" + c["text"] for c in chunks], emb)
        for c, v in zip(chunks, vecs):
            c["vec"] = v
        if not quiet:
            print(f"Embedded {len(chunks)} chunks with {emb}")
    elif not quiet:
        print("No embedding model loaded in LM Studio: index is BM25-only. "
              "Load one and re-run ingest to enable dense retrieval.")
    index = {"built": time.strftime("%Y-%m-%d %H:%M:%S"), "chunk_version": CHUNK_VERSION,
             "embed_model": emb, "files": files, "skipped": skipped,
             "chunks": chunks}
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=1, ensure_ascii=False)
    if not quiet:
        print(f"Indexed {len(files)} files into {len(chunks)} chunks -> {index_path}")
    return index

def load_index(matter):
    p = os.path.join(matter_dir(matter), "index.json")
    if not os.path.exists(p):
        sys.exit(f"No index for matter '{matter}'. Run: python3 ask.py --matter {matter} ingest")
    with open(p, encoding="utf-8") as f:
        return json.load(f)

# ---------------- BM25 search ----------------

def _chunk_tokens(c):
    return tokenize(c["text"] + " " + c["heading"] + " "
                    + re.sub(r"[/_\-.]", " ", c["file"]))

def bm25(chunks, query, top_k, stats_chunks=None):
    """Score `chunks`; compute corpus statistics (IDF, avg length) over
    `stats_chunks` (the FULL corpus) when given, so a scoped search keeps
    honest, comparable scores and the refusal gate stays calibrated."""
    k1, b = 1.5, 0.75
    docs = [_chunk_tokens(c) for c in chunks]
    stats_docs = docs if stats_chunks is None else [_chunk_tokens(c) for c in stats_chunks]
    n = len(stats_docs)
    avg = sum(len(d) for d in stats_docs) / max(n, 1)
    df = {}
    for d in stats_docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    scored = []
    for c, d in zip(chunks, docs):
        tf = {}
        for t in d:
            tf[t] = tf.get(t, 0) + 1
        s = 0.0
        for t in set(tokenize(query)):
            if t not in tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(d) / avg))
        scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    return scored[:top_k]

def source_key(chunk):
    """Diversity bucket for a chunk. Firm docs bucket by their top-level folder
    (firm-alpha, firm-bravo, ...). Root-level docs (e.g. context-summary.md) hold
    several firms in separate sections, so bucket those by file + heading."""
    f = chunk["file"]
    if "/" in f:
        return f.split("/", 1)[0]
    return f + " > " + (chunk.get("heading") or "")


def hybrid(chunks, question, top_k, stats_chunks, emb_model, diverse=False):
    """RRF-fuse BM25 and dense rankings. Returns (hits, bm_top, cos_top):
    hits = [(bm25_score, cos_or_None, chunk)] selected by fused rank.

    When diverse=True, selection takes the best chunk from each source first,
    then fills any remaining slots with the next-best chunks regardless of
    source. This stops one source (e.g. a long guide) from eating every slot on
    aggregate questions that must span multiple firms."""
    bm_ranked = bm25(chunks, question, len(chunks), stats_chunks=stats_chunks)
    bm_top = bm_ranked[0][0] if bm_ranked else 0.0
    bm_score = {c["id"]: s for s, c in bm_ranked}
    cos_top, cos_score = None, {}
    have_vecs = chunks and all("vec" in c for c in chunks)
    if emb_model and have_vecs:
        qv = embed_texts([question], emb_model, kind="search_query")[0]
        for c in chunks:
            cos_score[c["id"]] = sum(a * b for a, b in zip(qv, c["vec"]))
        cos_top = max(cos_score.values()) if cos_score else None
    K = 60          # standard reciprocal-rank-fusion constant
    W_DENSE = 0.5   # dense is the junior partner: gate key + tie-breaker,
                    # BM25 stays the primary ranker (see results 2026-08-26)
    rrf = {}
    for rank, (s, c) in enumerate(bm_ranked, 1):
        if s > 0:
            rrf[c["id"]] = rrf.get(c["id"], 0.0) + 1.0 / (K + rank)
    if cos_score:
        for rank, cid in enumerate(sorted(cos_score, key=lambda i: -cos_score[i]), 1):
            rrf[cid] = rrf.get(cid, 0.0) + W_DENSE / (K + rank)
    by_id = {c["id"]: c for c in chunks}
    ranked = sorted(rrf, key=lambda i: -rrf[i])
    if diverse:
        picked, seen = [], set()
        for i in ranked:                       # one best chunk per source
            k = source_key(by_id[i])
            if k not in seen:
                seen.add(k)
                picked.append(i)
            if len(picked) >= top_k:
                break
        if len(picked) < top_k:                # then fill, source no longer matters
            for i in ranked:
                if i not in picked:
                    picked.append(i)
                    if len(picked) >= top_k:
                        break
        top = picked[:top_k]
    else:
        top = ranked[:top_k]
    hits = [(bm_score.get(i, 0.0), cos_score.get(i), by_id[i]) for i in top]
    return hits, bm_top, cos_top

# ---------------- LM Studio ----------------

def http_json(url, payload=None, timeout=300):
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
    data = json.dumps(payload).encode() if payload is not None else None
    with urllib.request.urlopen(req, data, timeout=timeout) as r:
        return json.load(r)

def server_models():
    """Return (chat_model_id, embedding_model_id); either may be None."""
    try:
        ids = [m["id"] for m in (http_json(SERVER + "/models", timeout=5).get("data") or [])]
    except (urllib.error.URLError, OSError):
        return None, None
    chat = next((i for i in ids if "embed" not in i.lower()), None)
    emb = next((i for i in ids if "embed" in i.lower()), None)
    return chat, emb

def embed_texts(texts, model, kind="search_document"):
    """Embed texts via LM Studio /v1/embeddings; returns unit-normalized vectors.
    nomic models require task prefixes (search_document: / search_query:)."""
    if "nomic" in (model or "").lower():
        texts = [f"{kind}: {t}" for t in texts]
    vecs = []
    for i in range(0, len(texts), 32):
        out = http_json(SERVER + "/embeddings",
                        {"model": model, "input": texts[i:i + 32]})
        for d in out["data"]:
            v = d["embedding"]
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            vecs.append([round(x / norm, 5) for x in v])
    return vecs

def generate(system, user, model, on_token=None):
    """Stream the answer token by token. on_token prints as tokens arrive."""
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        # temp 0.0: greedy decode for a reproducible audit trail. A temperature
        # sweep (0.0-0.7) showed identical accuracy at every setting on this
        # corpus; 0.0 is the only fully deterministic one. See temp_sweep.py.
        "temperature": 0.0, "top_p": 0.8, "presence_penalty": 1.5,
        "max_tokens": 1200, "stream": True,
        "stream_options": {"include_usage": True},
    }
    req = urllib.request.Request(SERVER + "/chat/completions",
                                 json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    parts, usage = [], None
    with urllib.request.urlopen(req, timeout=300) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            if obj.get("usage"):
                usage = obj["usage"]
            ch = obj.get("choices") or []
            tok = ch[0].get("delta", {}).get("content") if ch else None
            if tok:
                parts.append(tok)
                if on_token:
                    on_token(tok)
    return "".join(parts).strip(), usage

# ---------------- verify ----------------

def verify_numbers(answer, source_text):
    """Every number in the answer must exist in the sources. Dumb code, no AI."""
    clean = re.sub(r"\[S\d+\]", "", answer)                    # drop citation labels
    clean = re.sub(r"(?m)^\s*\d+[.)]\s", "", clean)            # drop list markers
    norm_src = source_text.replace(",", "")
    warnings = []
    for num in set(re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", clean)):
        if num.replace(",", "") not in norm_src:
            warnings.append(f"UNVERIFIED NUMBER: {num}")
    return sorted(warnings)

# ---------------- ask ----------------

REFUSAL = "Not in the documents."

def ask(matter, question, top_k, min_score, quiet=False, only=None, batch=None, dense_min=0.5, diverse=False):
    index = load_index(matter)
    sk = index.get("skipped") or []
    if sk and not quiet:
        print(f"[coverage] {len(sk)} file(s) in this matter are NOT indexed and cannot be "
              f"seen: {', '.join(x['file'] for x in sk[:3])}"
              f"{' ...' if len(sk) > 3 else ''}", file=sys.stderr)
    chunks = index["chunks"]
    if only:
        chunks = [c for c in chunks if c["file"].startswith(only)]
        if not chunks:
            sys.exit(f"No indexed files under '{only}/'. Check the folder name, and re-run ingest.")
    chat_model, emb_model = server_models()
    if not index.get("embed_model"):
        emb_model = None  # index has no vectors; stay BM25-only
    hits, bm_top, cos_top = hybrid(chunks, question, top_k,
                                   index["chunks"] if only else None, emb_model,
                                   diverse=diverse)
    hits = [(s, cs, c) for s, cs, c in hits if s > 0 or (cs or 0) > 0]
    audit = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "matter": matter,
             "question": question, "only": only, "batch": batch,
             "top_score": round(bm_top, 3),
             "cos_top": round(cos_top, 3) if cos_top is not None else None,
             "dense": emb_model is not None,
             "chunks": [{"id": c["id"], "heading": c["heading"], "score": round(s, 3),
                         "cos": round(cs, 3) if cs is not None else None}
                        for s, cs, c in hits]}
    dense_ok = cos_top is not None and cos_top >= dense_min
    if not hits or (bm_top < min_score and not dense_ok):
        audit.update({"refused": True, "answer": REFUSAL, "warnings": [], "model": None})
        _log(matter, audit)
        print(REFUSAL)
        gate_msg = f"(bm25 {audit['top_score']} < gate {min_score}"
        if cos_top is not None:
            gate_msg += f", cosine {audit['cos_top']} < {dense_min}"
        print(gate_msg + "; the model was not called)")
        return audit
    model = chat_model
    if model is None:
        sys.exit("LM Studio server not reachable at 127.0.0.1:1234.\n"
                 "Open LM Studio > Developer tab > Start Server, and load a model.")
    with open(os.path.join(BASE, "prompt.txt"), encoding="utf-8") as f:
        system = f.read()
    src_lines = []
    for i, (s, cs, c) in enumerate(hits, 1):
        src_lines.append(f"[S{i}] {c['file']} > {c['heading'] or '(no heading)'}\n{c['text']}")
    user = "Sources:\n\n" + "\n\n".join(src_lines) + f"\n\n---\nQuestion: {question}"
    t0 = time.time()
    on_token = None
    if not quiet:
        def on_token(t):
            sys.stdout.write(t)
            sys.stdout.flush()
    answer, usage = generate(system, user, model, on_token)
    if not quiet:
        print()  # end the streamed line
    warnings = verify_numbers(answer, "\n".join(c["text"] for _, _, c in hits))
    audit.update({"refused": False, "answer": answer, "warnings": warnings,
                  "model": model, "latency_s": round(time.time() - t0, 1),
                  "usage": usage})
    _log(matter, audit)
    if not quiet:
        print("\n--- Sources ---")
        for i, (s, cs, c) in enumerate(hits, 1):
            extra = f", cos {cs:.2f}" if cs is not None else ""
            print(f"[S{i}] {c['file']} > {c['heading'] or '(no heading)'}  (bm25 {s:.2f}{extra})")
        for w in warnings:
            print(f"!!  {w}")
        if usage:
            pt = usage.get("prompt_tokens") or 0
            ct = usage.get("completion_tokens") or 0
            print(f"--- Context: {pt:,} prompt + {ct:,} answer = {pt+ct:,} / 32,768 ({(pt+ct)*100//32768}%) ---")
        else:
            print("--- Context: usage not reported by the server ---")
    return audit

def _log(matter, record):
    with open(os.path.join(matter_dir(matter), "audit.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

# ---------------- batch ----------------

def batch(matter, path, top_k, min_score, dense_min=0.5, diverse=False):
    if not os.path.exists(path):
        alt = os.path.join(matter_dir(matter), path)
        if os.path.exists(alt):
            path = alt
        else:
            sys.exit(f"Question file not found: {path}")
    tag = os.path.basename(path)
    lines = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            only, tk, dv = None, top_k, diverse   # per-line flags fall back to batch defaults
            if "::" in line:
                flagstr, _, line = line.partition("::")
                line = line.strip()
                if not line:
                    continue
                toks = flagstr.split()
                j = 0
                while j < len(toks):
                    t = toks[j]
                    if t == "--only" and j + 1 < len(toks):
                        only = toks[j + 1]; j += 2
                    elif t == "--top-k" and j + 1 < len(toks):
                        tk = int(toks[j + 1]); j += 2
                    elif t == "--diverse":
                        dv = True; j += 1
                    else:
                        sys.exit(f"Bad flag in questions file: {t!r} (line: {raw.strip()!r})")
            lines.append((only, tk, dv, line))
    if not lines:
        sys.exit(f"No questions in {path}")
    t0 = time.time()
    n_ans = n_gate = n_model_ref = n_warn = n_err = pt = ct = 0
    for i, (only, tk, dv, q) in enumerate(lines, 1):
        notes = []
        if only: notes.append(f"--only {only}")
        if tk != top_k: notes.append(f"top-k {tk}")
        if dv and not diverse: notes.append("diverse")
        head = f"[{i}/{len(lines)}]" + (f" ({', '.join(notes)})" if notes else "")
        print(f"\n{head} {q}")
        try:
            a = ask(matter, q, tk, min_score, only=only, batch=tag, dense_min=dense_min, diverse=dv)
        except (urllib.error.URLError, OSError) as e:
            n_err += 1
            print(f"!!  ERROR, question skipped: {e}")
            continue
        ans = (a.get("answer") or "").strip()
        if a.get("refused"):
            n_gate += 1
        elif ans == REFUSAL or ans.startswith("Not specified in the sources"):
            n_model_ref += 1
        else:
            n_ans += 1
        n_warn += len(a.get("warnings") or [])
        u = a.get("usage") or {}
        pt += u.get("prompt_tokens") or 0
        ct += u.get("completion_tokens") or 0
    mins = (time.time() - t0) / 60
    print(f"\n===== batch summary: {tag} =====")
    print(f"questions {len(lines)} | answered {n_ans} | refused {n_gate + n_model_ref} "
          f"(gate {n_gate}, model {n_model_ref}) | number warnings {n_warn} | errors {n_err}")
    print(f"tokens: {pt:,} prompt + {ct:,} answer | elapsed {mins:.1f} min")
    print(f"audit: matters/{matter}/audit.jsonl (lines tagged batch={tag})")

# ---------------- selftest ----------------

def selftest(min_score):
    ok = True
    def check(name, cond):
        nonlocal ok
        print(("PASS  " if cond else "FAIL  ") + name)
        ok = ok and cond
    print("== strata-v0 selftest (matter: fixtures) ==")
    index = ingest("fixtures", quiet=True)
    check("ingest built chunks", len(index["chunks"]) >= 3)
    table = [c for c in index["chunks"] if "Breakthrough" in c["text"]]
    check("table kept whole (Breakthrough + Main etch in one chunk)",
          bool(table) and "Main etch" in table[0]["text"])
    hits = bm25(index["chunks"], "metal-1 critical dimension CD", 5)
    check("search finds the CD chunk", bool(hits) and "1.2 nm" in hits[0][1]["text"])
    nonsense = bm25(index["chunks"], "purple elephant carburetor zeppelin", 5)
    top = nonsense[0][0] if nonsense else 0.0
    check(f"gate refuses nonsense (score {top:.2f} < {min_score})", top < min_score)
    w = verify_numbers("The CD is 1.2 nm and the budget is 999 C",
                       "\n".join(c["text"] for c in index["chunks"]))
    check("number check flags 999, passes 1.2", w == ["UNVERIFIED NUMBER: 999"])
    pptx = os.path.join(BASE, "matters", "fixtures", "docs", "grid-order.pptx")
    if os.path.exists(pptx):
        sl, _ = pptx_slides(pptx)
        body = "\n".join(sl[0][1]) if sl else ""
        pairs = all(f"{n}\n{v}" in body for n, v in
                    (("Alpha", "111"), ("Bravo", "222"), ("Charlie", "333")))
        check("pptx read in column order despite scrambled XML order", pairs)
        check("pptx speaker notes captured", "Delta is not a column" in body)
        pc = [c for c in index["chunks"] if c["file"].endswith(".pptx")]
        check("pptx chunks carry a 'slide N' heading",
              bool(pc) and any("slide 1" in c["heading"] for c in pc))
    else:
        check("pptx fixture present (run make_fixture_pptx.py)", False)

    with tempfile.TemporaryDirectory() as td:
        open(os.path.join(td, "seen.txt"), "w").write("hello")
        open(os.path.join(td, "unread.pdf"), "wb").write(b"%PDF-1.4 stub")
        open(os.path.join(td, "paired.pdf"), "wb").write(b"%PDF-1.4 stub")
        open(os.path.join(td, "paired.txt"), "w").write("converted text")
        idxable, skipped = scan_coverage(td)
        check("coverage flags an unconverted .pdf",
              [x["file"] for x in skipped] == ["unread.pdf"])
        check("coverage treats a .pdf with a .txt companion as covered",
              "paired.txt" in idxable and "paired.pdf" not in idxable)

    model, emb = server_models()
    if model:
        print(f"\nLM Studio server up (model: {model}, embeddings: {emb or 'none'}). Live test:")
        print("Q: What is the maximum thermal budget after metal-1?\n")
        ask("fixtures", "What is the maximum thermal budget after metal-1?", 5, min_score)
        print("\nQ (must refuse): What is the metal-1 CD in the shipment note?  -- skipped, run by hand if wanted")
    else:
        print("\nLM Studio server offline - live test skipped. (Developer tab > Start Server)")
    print("\n== selftest " + ("PASSED" if ok else "FAILED") + " ==")
    sys.exit(0 if ok else 1)

# ---------------- main ----------------

def main():
    ap = argparse.ArgumentParser(description="strata-v0: local cite-or-refuse Q&A")
    ap.add_argument("--matter", help="matter folder name under matters/")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--min-score", type=float, default=1.0,
                    help="refusal gate: refuse below this BM25 score (default 1.0)")
    ap.add_argument("--only", help="restrict search to files under this subfolder, e.g. --only adibi-ip")
    ap.add_argument("--dense-min", type=float, default=0.5,
                    help="dense gate: with embeddings, a cosine above this passes even when bm25 is low (default 0.5)")
    ap.add_argument("--diverse", action="store_true",
                    help="take the best chunk per source before filling slots; helps aggregate questions that span multiple firms")
    ap.add_argument("what", nargs="+",
                    help='"ingest", "coverage", "selftest", or a question')
    a = ap.parse_args()
    cmd = " ".join(a.what)
    if cmd == "selftest":
        selftest(a.min_score)
    elif cmd.startswith("batch"):
        if not a.matter: sys.exit("batch needs --matter <name>")
        parts = cmd.split(None, 1)
        if len(parts) < 2: sys.exit("usage: ask.py --matter <name> batch <questions.txt>")
        batch(a.matter, parts[1], a.top_k, a.min_score, dense_min=a.dense_min, diverse=a.diverse)
    elif cmd == "ingest":
        if not a.matter: sys.exit("ingest needs --matter <name>")
        ingest(a.matter)
    elif cmd == "coverage":
        if not a.matter: sys.exit("coverage needs --matter <name>")
        sys.exit(coverage(a.matter))
    else:
        if not a.matter: sys.exit("asking needs --matter <name>")
        ask(a.matter, cmd, a.top_k, a.min_score, only=a.only, dense_min=a.dense_min, diverse=a.diverse)

if __name__ == "__main__":
    main()
