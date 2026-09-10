#!/usr/bin/env python3
"""Build matters/counsel-2/docs/ from matters/counsel-2/source.json.

  python3 make_counsel2.py            # validate source.json (build check B1), then write docs/
  python3 make_counsel2.py check      # after `ask.py --matter counsel-2 ingest`: run the structural suite S1-S6
  python3 make_counsel2.py check --strict   # exit 1 on ANY red, not only on an unexpected one

The matter is a synthetic patent-counsel search: nine files are copied byte for byte
from matters/synthetic-counsel/docs/ (the frozen smoke set), fifteen are rendered from
the `docs` list in source.json, and notes/correspondence-register.md is generated from
the `timeline` so it cannot drift from the facts. Every currency amount in a rendered
body is a {{amount:<constant id>}} placeholder; build check B1 refuses to write anything
if a literal amount, an unknown date, or a string from `conventions.never_write` appears.

The .eml is written the way a person saves a received reply from Outlook: the newest
message on top with the earlier ones quoted below it in Outlook header blocks (the
`inner_rfc822` shape from make_thread_probe.py). The .docx is written with zipfile and
carries a real word/footnotes.xml, which is the structural suite's S1 target.
Stdlib only."""
import hashlib, html, json, os, re, shutil, sys, zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
MATTER = os.path.join(BASE, "matters", "counsel-2")
SOURCE = os.path.join(MATTER, "source.json")
DOCS = os.path.join(MATTER, "docs")
SMOKE_DOCS = os.path.join(BASE, "matters", "synthetic-counsel", "docs")
PLACEHOLDER = re.compile(r"\{\{(amount|text):([A-Za-z_0-9]+)\}\}")
ISO_DATE = re.compile(r"\b(20\d\d-\d\d-\d\d)\b")
LITERAL_AMOUNT = re.compile(r"(?:[$€]\s?\d[\d,]*|\b(?:USD|EUR)\s?\d[\d,]*|\b\d{1,3}(?:,\d{3})+\b)")
FOOTNOTE_REF = re.compile(r"\[\^(\d+)\]")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


# ---------------- rendering ----------------

def load_source():
    src = json.load(open(SOURCE, encoding="utf-8"))
    src["_ids"] = {c["id"]: c for c in src["constants"]}
    return src

def money(c):
    v = f"{c['value']:,}"
    return f"${v}" if c["currency"] == "USD" else f"{c['currency']} {v}"

def render(src, text, errors=None, where=""):
    def sub(m):
        kind, cid = m.group(1), m.group(2)
        c = src["_ids"].get(cid)
        if c is None:
            (errors if errors is not None else []).append(f"{where}: unknown constant {cid}")
            return "??"
        if kind == "amount":
            if c["kind"] != "amount":
                (errors if errors is not None else []).append(f"{where}: {cid} used as amount but kind={c['kind']}")
                return "??"
            return money(c)
        return str(c["value"])
    return PLACEHOLDER.sub(sub, text)

def doc_texts(d):
    """Every string of a doc entry that becomes document text."""
    if d["format"] in ("md", "txt"):
        yield d["body"]
    elif d["format"] == "eml":
        for m in d["messages"]:
            yield m["subject"]
            yield m["body"]
    elif d["format"] == "docx":
        for b in d["blocks"]:
            if b["type"] == "p":
                yield b["text"]
            else:
                for row in b["rows"]:
                    yield " | ".join(row)
        for fn in d.get("footnotes", []):
            yield fn["text"]


# ---------------- build check B1 ----------------

def build_check(src):
    errs = []
    ids = src["_ids"]
    dates_ok = {e["date"] for e in src["timeline"]} | {c["value"] for c in ids.values() if c["kind"] == "date"}
    never = src["conventions"]["never_write"]
    inherited = set(src["conventions"]["inherited_files"])
    paths = set()
    for d in src["docs"]:
        paths.add(d["path"])
        raw = "\n".join(doc_texts(d))
        if "{{TODO" in raw:
            errs.append(f"{d['path']}: TODO left in body")
        if "—" in raw:
            errs.append(f"{d['path']}: em dash")
        for m in LITERAL_AMOUNT.finditer(raw):
            errs.append(f"{d['path']}: literal amount '{m.group(0)}' (use a placeholder)")
        for m in ISO_DATE.finditer(raw):
            if m.group(1) not in dates_ok:
                errs.append(f"{d['path']}: date {m.group(1)} is not in the timeline or a date constant")
        rendered = render(src, raw, errs, d["path"])
        flat = rendered.replace(",", "")
        for nw in never:
            if nw in rendered or nw.replace(",", "") in flat:
                errs.append(f"{d['path']}: never_write '{nw}' present after render")
        declared = set(d.get("constant_ids") or [])
        used = {cid for _, cid in PLACEHOLDER.findall(raw)}
        if declared != used:
            errs.append(f"{d['path']}: constant_ids {sorted(declared)} != placeholders used {sorted(used)}")
    for c in ids.values():
        f = c.get("file")
        if f and f not in inherited | paths | {src["register"]["path"]}:
            errs.append(f"constant {c['id']}: file {f} has no doc")
        if f in paths and c["kind"] == "amount" and not c["inherited"]:
            d = next(x for x in src["docs"] if x["path"] == f)
            if f"{{{{amount:{c['id']}}}}}" not in "\n".join(doc_texts(d)):
                errs.append(f"constant {c['id']}: not placed in {f}")
    for e in src["timeline"]:
        if e["file"] and e["file"] not in inherited | paths:
            errs.append(f"timeline {e['date']} {e['party']}: file {e['file']} missing")
    for f in inherited:
        if not os.path.exists(os.path.join(SMOKE_DOCS, f)):
            errs.append(f"inherited file missing from synthetic-counsel: {f}")
    # substring safety over amounts, comma-stripped, excluding the accepted 500 cases
    amts = [(c["id"], str(c["value"])) for c in ids.values() if c["kind"] == "amount"]
    for a, va in amts:
        for b, vb in amts:
            if a != b and va != vb and va in vb and a != "gov_issue":
                errs.append(f"substring collision: {a}={va} inside {b}={vb}")
    return errs


# ---------------- writers ----------------

def write_text(rel, text):
    path = os.path.join(DOCS, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text.rstrip("\n") + "\n")

def write_eml(src, d):
    sys.path.insert(0, BASE)
    import make_thread_probe as mtp
    msgs = []
    for m in d["messages"]:
        mm = dict(m)
        mm["body"] = render(src, m["body"])
        msgs.append(mm)
    text = mtp.inner_rfc822({"messages": msgs})
    write_text(d["path"], text)

def _xml(s):
    return html.escape(s, quote=False)

def _runs(text):
    """Text with [^n] markers -> Word runs; a marker becomes a footnoteReference run."""
    out, pos = [], 0
    for m in FOOTNOTE_REF.finditer(text):
        if m.start() > pos:
            out.append(f'<w:r><w:t xml:space="preserve">{_xml(text[pos:m.start()])}</w:t></w:r>')
        out.append(f'<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteReference w:id="{m.group(1)}"/></w:r>')
        pos = m.end()
    if pos < len(text):
        out.append(f'<w:r><w:t xml:space="preserve">{_xml(text[pos:])}</w:t></w:r>')
    return "".join(out)

def _p(text, style=None):
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{ppr}{_runs(text)}</w:p>"

def _tbl(rows):
    out = "<w:tbl><w:tblPr><w:tblStyle w:val=\"TableGrid\"/></w:tblPr>"
    for row in rows:
        out += "<w:tr>" + "".join(f"<w:tc>{_p(c)}</w:tc>" for c in row) + "</w:tr>"
    return out + "</w:tbl>"

def write_docx(src, d):
    body = ""
    for b in d["blocks"]:
        if b["type"] == "p":
            body += _p(render(src, b["text"]), b.get("style") if b.get("style") != "Normal" else None)
        else:
            body += _tbl([[render(src, c) for c in row] for row in b["rows"]])
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           f'<w:document xmlns:w="{W}"><w:body>{body}<w:sectPr/></w:body></w:document>')
    notes = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:footnotes xmlns:w="{W}">'
             f'<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>'
             f'<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>')
    for fn in d.get("footnotes", []):
        notes += (f'<w:footnote w:id="{fn["n"]}"><w:p><w:pPr><w:pStyle w:val="FootnoteText"/></w:pPr>'
                  f'<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteRef/></w:r>'
                  f'<w:r><w:t xml:space="preserve"> {_xml(render(src, fn["text"]))}</w:t></w:r></w:p></w:footnote>')
    notes += "</w:footnotes>"
    styles = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="{W}">'
              + "".join(f'<w:style w:type="paragraph" w:styleId="{s}"><w:name w:val="{n}"/></w:style>'
                        for s, n in (("Title", "Title"), ("Heading1", "heading 1"), ("Heading2", "heading 2"),
                                     ("ListParagraph", "List Paragraph"), ("FootnoteText", "footnote text")))
              + '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/></w:style></w:styles>')
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
          '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
          '<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>'
          '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')
    drels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
             '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/>'
             '</Relationships>')
    path = os.path.join(DOCS, d["path"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in (("[Content_Types].xml", ct), ("_rels/.rels", rels),
                           ("word/_rels/document.xml.rels", drels), ("word/document.xml", doc),
                           ("word/styles.xml", styles), ("word/footnotes.xml", notes)):
            # a fixed entry timestamp keeps the .docx byte-identical across builds
            zi = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, data)

def register_text(src):
    names = {p["id"]: p["name"] for p in src["parties"]}
    rows = [e for e in src["timeline"] if e["kind"] in ("message", "call")]
    out = ["# Correspondence register: patent counsel search (SYNTHETIC TEST DATA)", "",
           f"Maintained by the TestCo applicant team. One row per message sent or received,",
           f"and per call held, as of {src['matter']['as_of']}. A firm with no 'in' row has not",
           "replied. Generated from source.json; do not edit by hand.", "",
           "| Date | Direction | Firm | Subject |", "|---|---|---|---|"]
    for e in rows:
        out.append(f"| {e['date']} | {e['direction']} | {names[e['party']]} | {e['subject']} |")
    silent = [names[p["id"]] for p in src["parties"]
              if p["folder"] and p["folder"].startswith("firm")
              and not any(e["party"] == p["id"] and e["direction"] == "in" for e in rows)]
    out += ["", "## Firms with no reply on file", ""]
    out += [f"- {n}" for n in silent] or ["- none"]
    return "\n".join(out) + "\n"

def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()

def build(src):
    errs = build_check(src)
    if errs:
        print(f"BUILD CHECK B1 FAILED, {len(errs)} error(s); nothing written")
        for e in errs:
            print(" -", e)
        return 1
    if os.path.isdir(DOCS):
        shutil.rmtree(DOCS)
    written = []
    for rel in src["conventions"]["inherited_files"]:
        dst = os.path.join(DOCS, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(SMOKE_DOCS, rel), dst)
        assert sha(dst) == sha(os.path.join(SMOKE_DOCS, rel))
        written.append((rel, "inherited"))
    for d in src["docs"]:
        if d["format"] in ("md", "txt"):
            write_text(d["path"], render(src, d["body"]))
        elif d["format"] == "eml":
            write_eml(src, d)
        elif d["format"] == "docx":
            write_docx(src, d)
        else:
            raise SystemExit(f"unknown format {d['format']} for {d['path']}")
        written.append((d["path"], d["format"]))
    write_text(src["register"]["path"], register_text(src))
    written.append((src["register"]["path"], "generated register"))
    manifest = {"source_sha256": sha(SOURCE), "source_version": src.get("version"),
                "files": [{"path": p, "kind": k, "sha256": sha(os.path.join(DOCS, p))} for p, k in written]}
    with open(os.path.join(MATTER, "build.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    print(f"counsel-2: wrote {len(written)} files under {os.path.relpath(DOCS, BASE)} "
          f"({len(src['conventions']['inherited_files'])} inherited, {len(src['docs'])} rendered, 1 register); "
          f"build.json records the hashes. Next: python3 ask.py --matter counsel-2 ingest")
    return 0


# ---------------- structural suite ----------------

def check(src, strict=False):
    sys.path.insert(0, BASE)
    import ask
    idx_path = os.path.join(MATTER, "index.json")
    if not os.path.exists(idx_path):
        print("no index.json: run `python3 ask.py --matter counsel-2 ingest` first")
        return 1
    idx = json.load(open(idx_path, encoding="utf-8"))
    chunks = idx["chunks"]
    docx_rel = "firm-juliett/proposal.docx"
    eml_rel = "firm-india/reply.eml"
    with zipfile.ZipFile(os.path.join(DOCS, docx_rel)) as z:
        fn_xml = z.read("word/footnotes.xml").decode("utf-8")
    in_index = lambda s, f=None: any(s in c["text"] for c in chunks if f is None or c["file"] == f)
    skipped = idx.get("skipped") or []
    partial = {s["file"] for s in skipped if s.get("partial")}
    missing = {s["file"] for s in skipped if not s.get("partial")}
    footnote_indexed = in_index("per patent family", docx_rel)
    eml_chunks = [c for c in chunks if c["file"] == eml_rel and c.get("email")]
    msg_ns = sorted({c["email"]["n"] for c in eml_chunks if not c["email"].get("overview")})
    msg_dates = [c["email"]["date"] for n in msg_ns for c in eml_chunks if c["email"].get("n") == n][:len(msg_ns)]
    overview = [c for c in eml_chunks if c["email"].get("overview")]
    disk = set()
    for root, _, files in os.walk(DOCS):
        for f in files:
            if not f.startswith((".", "~$")):
                disk.add(os.path.relpath(os.path.join(root, f), DOCS))
    indexed_files = {c["file"] for c in chunks}
    results = [
        ("S1", "footnote 2 ('per patent family') is in word/footnotes.xml AND in some index chunk of the .docx",
         "per patent family" in fn_xml and footnote_indexed, "RED"),
        ("S2", "coverage's PARTIAL flag on the .docx agrees with S1 (named partial iff the footnote is not indexed)",
         (docx_rel in partial) == (not footnote_indexed), "GREEN"),
        ("S3", "Schedule B 'expedited filing' is indexed under the .docx (after the signature block)",
         in_index("expedited filing", docx_rel) or in_index("Expedited filing", docx_rel), "GREEN"),
        ("S4", ".eml yields message chunks n=1,2,3 in date order plus one thread-overview chunk",
         msg_ns == [1, 2, 3] and msg_dates == sorted(msg_dates) and len(overview) == 1, "GREEN"),
        ("S5", "--only firm-alpha excludes every firm-alpha-ip/ file (in_scope boundary)",
         not any(ask.in_scope(f, "firm-alpha") for f in indexed_files if f.startswith("firm-alpha-ip/")), "GREEN"),
        ("S6", "every file under docs/ is indexed or named by coverage as missing",
         disk <= (indexed_files | missing), "GREEN"),
    ]
    bad = 0
    for sid, text, ok, expected in results:
        state = "GREEN" if ok else "RED"
        flag = "" if state == expected else "   <-- UNEXPECTED"
        if state == "RED" and (strict or state != expected):
            bad += 1
        print(f"{sid} {state:5} (expected day one: {expected}){flag}  {text}")
    if not footnote_indexed:
        print("note: S1 red means the .docx footnote parser has not landed; the class 8 refusal item is live.")
    extra = disk - indexed_files - missing
    if extra:
        print("S6 detail, on disk but nowhere:", sorted(extra))
    return 1 if bad else 0


def main():
    src = load_source()
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        sys.exit(check(src, strict="--strict" in sys.argv))
    sys.exit(build(src))

if __name__ == "__main__":
    main()
