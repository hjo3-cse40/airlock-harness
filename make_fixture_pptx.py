#!/usr/bin/env python3
"""Build matters/fixtures/docs/grid-order.pptx, a parser regression fixture.

Ground truth: three columns, each holding a NAME then its VALUE. The shapes are
written to XML in deliberately SCRAMBLED order (all names, then all values, and
the columns out of order) so that any parser trusting document order will pair
the wrong name with the wrong value. Reading it correctly must yield
Alpha->111, Bravo->222, Charlie->333, each pair adjacent.

Parser fixture only. It is not a PowerPoint-openable deck.
"""
import os, zipfile

EMU_IN = 914400
SLIDE_W, SLIDE_H = 12192000, 6858000

def shape(sid, name, x, y, cx, cy, text):
    return f'''<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{name}"/><p:cNvSpPr/>
<p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/>
<a:ext cx="{cx}" cy="{cy}"/></a:xfrm></p:spPr>
<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>'''

COLS = [("Alpha", "111"), ("Bravo", "222"), ("Charlie", "333")]
xs = [1 * EMU_IN, 5 * EMU_IN, 9 * EMU_IN]
shapes = [shape(2, "Title", 0, 200000, SLIDE_W, 800000, "Quarterly Comparison")]
# scrambled: values first and columns reversed, names after in another order
for i in (2, 0, 1):
    shapes.append(shape(10 + i, f"val{i}", xs[i], 3 * EMU_IN, 2 * EMU_IN,
                        600000, COLS[i][1]))
for i in (1, 2, 0):
    shapes.append(shape(20 + i, f"name{i}", xs[i], 2 * EMU_IN, 2 * EMU_IN,
                        600000, COLS[i][0]))
shapes.append(shape(30, "Footer", 0, 6200000, SLIDE_W, 400000, "Fixture footer"))

slide = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
         ' xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
         '<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/>'
         '<p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>' + "".join(shapes) +
         '</p:spTree></p:cSld></p:sld>')

notes = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<p:notes xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
         ' xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
         '<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/>'
         '<p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>' +
         shape(2, "Notes", 0, 0, SLIDE_W, 400000,
               "Speaker note: Delta is not a column.") +
         '</p:spTree></p:cSld></p:notes>')

pres = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
        ' xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        f'<p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}"/></p:presentation>')

ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      '<Default Extension="xml" ContentType="application/xml"/></Types>')

out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "matters", "fixtures", "docs", "grid-order.pptx")
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", ct)
    z.writestr("ppt/presentation.xml", pres)
    z.writestr("ppt/slides/slide1.xml", slide)
    z.writestr("ppt/notesSlides/notesSlide1.xml", notes)
print("wrote", out)
