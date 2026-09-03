#!/usr/bin/env python3
"""Build the document-format fixtures. Synthetic content only. Two outputs:

1. matters/fixtures/docs/styles.docx and thread.eml, parser regression fixtures
   read by selftest (heading styles, a list, a table, an email heading).
2. matters/format-probe/, a small synthetic matter where every file is a
   DIFFERENT format (.pdf .doc .rtf .html .docx .eml plus one .msg stub), with
   test-questions.txt and ANSWER-KEY.md, so a live batch run proves that every
   format is retrieved and cited, not just parsed.

The .docx files are written here with zipfile (no dependency). The .doc, .rtf,
.html and .pdf files are produced by the local macOS tools textutil and
cupsfilter when present; on another OS those steps are skipped and the
committed copies stay in use. Ingest sidecars (.txt/.docx made from the
sources) and the .derived.json manifest are git-ignored on purpose, so a fresh
clone exercises the conversion path.
"""
import os, shutil, subprocess, zipfile
from email.message import EmailMessage

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "matters", "fixtures", "docs")
PROBE = os.path.join(HERE, "matters", "format-probe")

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

def _p(text, style=None, numbered=False):
    ppr = ""
    if style or numbered:
        ppr = "<w:pPr>"
        if style:
            ppr += f'<w:pStyle w:val="{style}"/>'
        if numbered:
            ppr += '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'
        ppr += "</w:pPr>"
    return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'

def _tbl(rows):
    out = "<w:tbl>"
    for row in rows:
        out += "<w:tr>" + "".join(f"<w:tc>{_p(c)}</w:tc>" for c in row) + "</w:tr>"
    return out + "</w:tbl>"

def write_docx(path, body_xml):
    """Minimal .docx: enough for Word, textutil and our parser to open it."""
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           f'<w:document xmlns:w="{W}"><w:body>{body_xml}<w:sectPr/></w:body></w:document>')
    styles = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="{W}">'
              + "".join(f'<w:style w:type="paragraph" w:styleId="{s}"><w:name w:val="{n}"/></w:style>'
                        for s, n in (("Title", "Title"), ("Heading1", "heading 1"),
                                     ("Heading2", "heading 2"), ("ListParagraph", "List Paragraph")))
              + "</w:styles>")
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
          '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
          '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')
    drels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
             '</Relationships>')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/_rels/document.xml.rels", drels)
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", styles)

def write_eml(path, sender, to, date, subject, body, attachment=None):
    m = EmailMessage()
    m["From"], m["To"], m["Date"], m["Subject"] = sender, to, date, subject
    m.set_content(body)
    if attachment:
        m.add_attachment(b"%PDF-1.4 stub", maintype="application", subtype="pdf",
                         filename=attachment)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(bytes(m))

def _textutil(src, fmt, dst):
    if shutil.which("textutil"):
        subprocess.run(["textutil", "-convert", fmt, "-output", dst, src], check=True)
        return True
    return False

def _pdf(src, dst):
    if shutil.which("cupsfilter"):
        with open(dst, "wb") as f:
            subprocess.run(["cupsfilter", src], stdout=f, stderr=subprocess.DEVNULL, check=True)
        return True
    return False

def build_fixtures():
    write_docx(os.path.join(FIX, "styles.docx"),
               _p("Engagement Memo", "Title")
               + _p("Fees", "Heading1")
               + _p("Firm Kilo quotes 3,150 dollars for a provisional filing.")
               + _p("Conditions", "Heading2")
               + _p("Fixed fee covers one round of revisions.", numbered=True)
               + _p("Government fees are billed at cost.", numbered=True)
               + _tbl([["Service", "Fee"], ["Design patent", "1,975 dollars"],
                       ["Trademark search", "640 dollars"]])
               + _p("Prepared by Firm Kilo."))
    write_eml(os.path.join(FIX, "thread.eml"),
              "P. Okafor (Firm Lima) <p.okafor@firm-lima.example>",
              "TestCo <patents@testco.example>",
              "Tue, 18 Aug 2026 09:15:00 -0700",
              "Re: engagement terms",
              "Firm Lima can start after a retainer of 2,400 dollars is received.\n\n"
              "Our fee proposal is attached.\n",
              attachment="lima-proposal.pdf")

def build_probe():
    docs = os.path.join(PROBE, "docs")
    tmp = os.path.join(PROBE, ".src")
    os.makedirs(tmp, exist_ok=True)
    def txt(name, text):
        p = os.path.join(tmp, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p
    def out(*parts):
        p = os.path.join(docs, *parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    _pdf(txt("fee-letter.txt",
             "Firm Zulu fee letter\n\nFirm Zulu quotes 4,321 dollars for a provisional "
             "application and 11,850 dollars for a utility application, small entity.\n"),
         out("firm-zulu", "fee-letter.pdf"))
    _textutil(txt("engagement.txt",
                  "Firm Yankee engagement letter\n\nFirm Yankee requires a retainer of "
                  "2,750 dollars before any work begins. The retainer is not a service fee.\n"),
              "doc", out("firm-yankee", "engagement.doc"))
    _textutil(txt("terms.txt",
                  "Firm Xray terms\n\nFirm Xray bills 415 dollars per hour for office action "
                  "responses, capped at 3,300 dollars per response.\n"),
              "rtf", out("firm-xray", "terms.rtf"))
    with open(out("firm-uniform", "notes.html"), "w", encoding="utf-8") as f:
        f.write("<html><body><h1>Firm Uniform call notes</h1><p>Firm Uniform offers a "
                "15 percent volume discount above ten filings per year.</p>"
                "<p>No written quote yet.</p></body></html>")
    write_docx(out("firm-whiskey", "proposal.docx"),
               _p("Firm Whiskey proposal", "Title")
               + _p("Fee schedule", "Heading1")
               + _tbl([["Service", "Fee"], ["Provisional application", "3,900 dollars"],
                       ["Design patent", "1,975 dollars"], ["Utility application", "12,600 dollars"]])
               + _p("Terms", "Heading1")
               + _p("Fees are fixed for filings started within 12 months.", numbered=True))
    write_eml(out("firm-victor", "reply.eml"),
              "R. Chen (Firm Victor) <r.chen@firm-victor.example>",
              "TestCo <patents@testco.example>",
              "Fri, 21 Aug 2026 14:02:00 -0700",
              "Re: patent counsel inquiry",
              "Thank you for the inquiry. Firm Victor must decline the engagement because "
              "of a conflict of interest with an existing client.\n\nRegards,\nR. Chen\n",
              attachment="conflict-notice.pdf")
    with open(out("firm-tango", "legacy.msg"), "wb") as f:
        f.write(b"\xd0\xcf\x11\xe0 stub Outlook message, not readable by design")
    shutil.rmtree(tmp)
    with open(os.path.join(PROBE, "test-questions.txt"), "w", encoding="utf-8") as f:
        f.write("# format-probe: one file per format. Expected answers in ANSWER-KEY.md\n"
                "What does Firm Zulu quote for a provisional application?\n"
                "What retainer does Firm Yankee require before work begins?\n"
                "What is Firm Xray's hourly rate for office action responses?\n"
                "What discount does Firm Uniform offer above ten filings?\n"
                "What does Firm Whiskey charge for a design patent?\n"
                "Did Firm Victor accept the engagement?\n"
                "What fee did Firm Tango quote?\n")
    with open(os.path.join(PROBE, "ANSWER-KEY.md"), "w", encoding="utf-8") as f:
        f.write("# format-probe answer key (never ingested)\n\n"
                "| # | Source format | Expected |\n|---|---|---|\n"
                "| 1 | .pdf (pdftotext sidecar) | 4,321 dollars, cited to firm-zulu/fee-letter.txt page 1 |\n"
                "| 2 | .doc (textutil -> .docx) | 2,750 dollars retainer, cited to firm-yankee/engagement.docx |\n"
                "| 3 | .rtf (textutil -> .docx) | 415 dollars per hour, cited to firm-xray/terms.docx |\n"
                "| 4 | .html (textutil -> .docx) | 15 percent, cited to firm-uniform/notes.docx |\n"
                "| 5 | .docx native, table row | 1,975 dollars, cited to firm-whiskey/proposal.docx > Fee schedule |\n"
                "| 6 | .eml native | No, declined for a conflict of interest, cited to firm-victor/reply.eml |\n"
                "| 7 | .msg stub (never indexed) | REFUSE: Firm Tango has no readable document |\n")

if __name__ == "__main__":
    build_fixtures()
    build_probe()
    print("fixtures:", sorted(os.listdir(FIX)))
    for root, _, names in os.walk(os.path.join(PROBE, "docs")):
        for n in sorted(names):
            print("probe:", os.path.relpath(os.path.join(root, n), PROBE))
