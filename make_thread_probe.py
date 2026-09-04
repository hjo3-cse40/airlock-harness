#!/usr/bin/env python3
"""Build matters/thread-probe/: a synthetic, public-safe email chain whose second
message is a long reply from a director, saved the way a person saves one from
Outlook (forward the whole thread to yourself, then Save As .eml), plus three
distractor documents, the questions file and the answer key.

  python3 make_thread_probe.py                 # docs/ + test-questions.txt + ANSWER-KEY.md + answer-key.json
  python3 make_thread_probe.py --pad 580000    # pad the .eml with base64 attachment stubs to about this size
  python3 make_thread_probe.py --variants DIR  # also write the same chain in six quoting styles under DIR/<style>/docs/

Everything comes from matters/thread-probe/source.json (messages, distractor docs,
questions). The chain is fiction about a community garden; no real names, no real
organisations. Stdlib only."""
import base64, datetime, email.utils, html as htmlmod, json, os, random, re, sys

BASE = os.path.dirname(os.path.abspath(__file__))
MATTER = os.path.join(BASE, "matters", "thread-probe")
SOURCE = os.path.join(MATTER, "source.json")
EML_NAME = "thread.eml"

def party(m, who):
    name, addr = m.get(f"{who}_name") or "", m.get(f"{who}_addr") or ""
    return f"{name} <{addr}>" if name and addr else (name or addr)

def iso_day(s):
    return (s or "")[:10]

def when(m):
    d = email.utils.parsedate_to_datetime(m["date_rfc2822"])
    return d

def outlook_sent(m):
    d = when(m)
    return d.strftime("%A, %B ") + str(d.day) + d.strftime(", %Y ") + d.strftime("%I:%M %p").lstrip("0")

def gmail_on(m):
    d = when(m)
    return d.strftime("%a, %b ") + str(d.day) + d.strftime(", %Y at ") + d.strftime("%I:%M %p").lstrip("0")

def apple_on(m):
    d = when(m)
    return d.strftime("%b ") + str(d.day) + d.strftime(", %Y, at ") + d.strftime("%I:%M %p").lstrip("0")

def korean_sent(m):
    d = when(m)
    wd = "월화수목금토일"[d.weekday()]
    return f"{d.year}년 {d.month}월 {d.day}일 {wd}요일 {'오전' if d.hour < 12 else '오후'} {d.hour % 12 or 12}:{d.minute:02d}"

def outlook_block(m, korean=False):
    keys = ("보낸 사람", "보낸 날짜", "받는 사람", "참조", "제목") if korean else ("From", "Sent", "To", "Cc", "Subject")
    sent = korean_sent(m) if korean else outlook_sent(m)
    lines = [f"{keys[0]}: {party(m, 'from')}", f"{keys[1]}: {sent}", f"{keys[2]}: {party(m, 'to')}"]
    if m.get("cc_addr"):
        lines.append(f"{keys[3]}: {party(m, 'cc')}")
    lines.append(f"{keys[4]}: {m['subject']}")
    return lines

def outlook_plain(chain, korean=False):
    out = [chain["forward"]["note"], ""]
    for m in reversed(chain["messages"]):
        out += ["", "________________________________"] + outlook_block(m, korean) + [""] + m["body"].splitlines()
    return "\n".join(out) + "\n"

def outlook_html(chain):
    def p(s):
        return f"<p class=MsoNormal>{htmlmod.escape(s) if s.strip() else '&nbsp;'}</p>"
    parts = ["<html><head><meta charset='utf-8'></head><body lang=EN-US>", p(chain["forward"]["note"]), p("")]
    for m in reversed(chain["messages"]):
        blk = outlook_block(m)
        parts.append("<div style='border:none;border-top:solid #E1E1E1 1.0pt;padding:3.0pt 0in 0in 0in'>"
                     "<p class=MsoNormal>" + "<br>".join(
                         f"<b>{htmlmod.escape(l.split(':', 1)[0])}:</b> {htmlmod.escape(l.split(':', 1)[1].strip())}"
                         for l in blk) + "</p></div>")
        parts.append(p(""))
        parts += [p(line) for line in m["body"].splitlines()]
    parts.append("</body></html>")
    return "\n".join(parts)

def quote(text):
    return "\n".join(("> " + l).rstrip() for l in text.splitlines())

def nested_plain(chain, apple=False):
    msgs = chain["messages"]
    def intro(m):
        return (f"On {apple_on(m)}, {party(m, 'from')} wrote:" if apple
                else f"On {gmail_on(m)} {party(m, 'from')}\nwrote:")
    def nest(k):
        body = msgs[k]["body"]
        if k > 0:
            body += "\n\n" + intro(msgs[k - 1]) + "\n" + quote(nest(k - 1))
        return body
    return chain["forward"]["note"] + "\n\n" + intro(msgs[-1]) + "\n" + quote(nest(len(msgs) - 1)) + "\n"

def inner_rfc822(chain):
    msgs = chain["messages"]
    last = msgs[-1]
    body = [last["body"]]
    for m in reversed(msgs[:-1]):
        body += ["", "________________________________"] + outlook_block(m) + [""] + m["body"].splitlines()
    heads = [f"From: {party(last, 'from')}", f"To: {party(last, 'to')}"]
    if last.get("cc_addr"):
        heads.append(f"Cc: {party(last, 'cc')}")
    heads += [f"Date: {last['date_rfc2822']}", f"Subject: {last['subject']}", "MIME-Version: 1.0",
              'Content-Type: text/plain; charset="utf-8"', "Content-Transfer-Encoding: 8bit", "", ""]
    return "\n".join(heads) + "\n".join(body) + "\n"

def b64_stub(nbytes, seed):
    rnd = random.Random(seed)
    raw = b"%PDF-1.4 stub " + bytes(rnd.getrandbits(8) for _ in range(max(0, nbytes)))
    enc = base64.b64encode(raw).decode()
    return "\n".join(enc[i:i + 76] for i in range(0, len(enc), 76))

def build_eml(chain, body, kind, attachments, pad, seed):
    fw = chain["forward"]
    boundary = f"===============ThreadProbe{seed}=="
    heads = [f"From: {fw['from_name']} <{fw['from_addr']}>", f"To: {fw['to_name']} <{fw['to_addr']}>",
             f"Date: {fw['date_rfc2822']}", f"Subject: {fw['subject']}", "MIME-Version: 1.0",
             f'Content-Type: multipart/mixed; boundary="{boundary}"', "", ""]
    parts = []
    if kind == "html":
        parts.append(f"--{boundary}\nContent-Type: text/html; charset=\"utf-8\"\nContent-Transfer-Encoding: 8bit\n\n{body}\n")
    elif kind == "attached":
        parts.append(f"--{boundary}\nContent-Type: text/plain; charset=\"utf-8\"\nContent-Transfer-Encoding: 8bit\n\n{fw['note']}\n")
        parts.append(f"--{boundary}\nContent-Type: message/rfc822\nContent-Disposition: attachment; filename=\"thread.eml\"\n\n{body}\n")
    else:
        parts.append(f"--{boundary}\nContent-Type: text/plain; charset=\"utf-8\"\nContent-Transfer-Encoding: 8bit\n\n{body}\n")
    head_len = sum(len(p) for p in parts) + len("\n".join(heads))
    per = (max(0, (pad - head_len - 400 * max(1, len(attachments))) * 3 // 4 // max(1, len(attachments)))
           if pad else 24)
    for i, name in enumerate(attachments):
        parts.append(f"--{boundary}\nContent-Type: application/pdf\nContent-Transfer-Encoding: base64\n"
                     f"Content-Disposition: attachment; filename=\"{name}\"\nMIME-Version: 1.0\n\n{b64_stub(per, seed + i)}\n")
    return "\n".join(heads) + "\n".join(parts) + f"--{boundary}--\n"

def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def answer_key_md(questions):
    out = ["# Answer key: thread-probe (%d questions)" % len(questions), "",
           "PASS = the answer contains the expected facts (numbers and dates exactly as written in the",
           "message) and cites thread.eml. REFUSE = the honest answer is that the thread does not say.",
           "Summary questions pass when at least `min_facts` of the listed key points appear.",
           "`eval_thread_probe.py` scores a batch run against `answer-key.json` deterministically.", "",
           "| # | Type | Category | Question | Expected |", "|---|---|---|---|---|"]
    for q in questions:
        out.append(f"| {q['n']} | {q['type']} | {q['category']} | {q['text'].replace('|', '/')} | {q['expected'].replace('|', '/')} |")
    return "\n".join(out) + "\n"

def main():
    pad = int(sys.argv[sys.argv.index("--pad") + 1]) if "--pad" in sys.argv else 0
    variants = sys.argv[sys.argv.index("--variants") + 1] if "--variants" in sys.argv else None
    src = json.load(open(SOURCE, encoding="utf-8"))
    chain = {"forward": src["forward"], "messages": src["messages"]}
    atts = sorted({a for m in chain["messages"] for a in (m.get("attachments") or [])})
    docs = os.path.join(MATTER, "docs")
    write(os.path.join(docs, EML_NAME), build_eml(chain, outlook_plain(chain), "plain", atts, pad, 1000))
    for d in src["docs"]:
        write(os.path.join(docs, d["filename"]), d["text"].rstrip() + "\n")
    qs = src["questions"]
    lines = ["# thread-probe: a self-forwarded chain whose second message is a long reply. Key in ANSWER-KEY.md"]
    for q in qs:
        flags = (q.get("flags") or "").strip()
        lines.append(f"{flags} :: {q['text']}" if flags else q["text"])
    write(os.path.join(MATTER, "test-questions.txt"), "\n".join(lines) + "\n")
    write(os.path.join(MATTER, "ANSWER-KEY.md"), answer_key_md(qs))
    write(os.path.join(MATTER, "answer-key.json"), json.dumps({"questions": qs}, indent=1, ensure_ascii=False) + "\n")
    print(f"thread-probe: {EML_NAME} {os.path.getsize(os.path.join(docs, EML_NAME)):,} bytes, "
          f"{len(src['docs'])} distractor docs, {len(qs)} questions")
    if variants:
        styles = {"outlook-plain": ("plain", outlook_plain(chain)), "outlook-html": ("html", outlook_html(chain)),
                  "gmail-plain": ("plain", nested_plain(chain)), "apple-plain": ("plain", nested_plain(chain, apple=True)),
                  "outlook-korean": ("plain", outlook_plain(chain, korean=True)),
                  "forward-attached": ("attached", inner_rfc822(chain))}
        for i, (name, (kind, body)) in enumerate(styles.items()):
            p = os.path.join(variants, name, "docs", EML_NAME)
            write(p, build_eml(chain, body, kind, atts, pad, 2000 + i))
            for d in src["docs"]:
                write(os.path.join(variants, name, "docs", d["filename"]), d["text"].rstrip() + "\n")
            print(f"variant {name}: {os.path.getsize(p):,} bytes")

if __name__ == "__main__":
    main()
