# format-probe answer key (never ingested)

| # | Source format | Expected |
|---|---|---|
| 1 | .pdf (pdftotext sidecar) | 4,321 dollars, cited to firm-zulu/fee-letter.txt page 1 |
| 2 | .doc (textutil -> .docx) | 2,750 dollars retainer, cited to firm-yankee/engagement.docx |
| 3 | .rtf (textutil -> .docx) | 415 dollars per hour, cited to firm-xray/terms.docx |
| 4 | .html (textutil -> .docx) | 15 percent, cited to firm-uniform/notes.docx |
| 5 | .docx native, table row | 1,975 dollars, cited to firm-whiskey/proposal.docx > Fee schedule |
| 6 | .eml native | No, declined for a conflict of interest, cited to firm-victor/reply.eml |
| 7 | .msg stub (never indexed) | REFUSE: Firm Tango has no readable document |
