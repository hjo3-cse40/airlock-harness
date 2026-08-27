# Answer key: synthetic-counsel test set (36 questions)

Marks: PASS = correct + cited to the listed source. REFUSE = must answer
"Not in the documents." / "Not specified in the sources." Any invented
number or wrong-firm citation = FAIL.

| # | Flag | Expected result | Expected source |
|---|------|-----------------|-----------------|
| 1 | - | $4,800 | firm-alpha/fee-proposal.md (or context-summary) |
| 2 | - | $12,200 | firm-alpha/fee-proposal.md |
| 3 | - | $2,900 | firm-alpha/fee-proposal.md |
| 4 | - | $7,400 | firm-alpha/fee-proposal.md |
| 5 | - | 3 in 2026, 4 in 2027, 6 in 2028, 7 in 2029 (20 total) | context-summary.md |
| 6 | - | about $3,000 per patent | context-summary.md |
| 7 | - | Firm Echo; existing client relationship in the same technology space = conflict of interest | firm-echo/email-rejection.md or context-summary |
| 8 | - | 2026-08-19 | firm-delta/email-initial.md or context-summary |
| 9 | --only firm-alpha | all four: $4,800 / $12,200 / $7,400 / $2,900 | fee-proposal.md |
| 10 | --only firm-bravo | $6,100 flat, drawings included | email-initial.md |
| 11 | --only firm-bravo | utility quoted after a scope review of first two disclosures; no flat number | email-initial.md |
| 12 | --only firm-charlie | REFUSE (no fee quoted; schedule follows conflicts check). Saying "no fee yet" with citation also passes | - |
| 13 | --only firm-charlie | typical provisional pendency = 12 months | guide, page 7 |
| 14 | --only firm-charlie | $130 (small entity provisional government fee) | guide, page 12 (table) |
| 15 | --only firm-echo | existing client relationship, same technology space, conflict of interest | email-rejection.md |
| 16 | --only firm-delta | No. Two OUTBOUND messages (8/12 initial, 8/19 follow-up), no reply from the firm | email-initial.md |
| 17 | - | Alpha, Bravo, Charlie responded; Echo replied only to decline; Delta silent. Any cited subset naming Alpha+Bravo+Charlie passes | context-summary.md |
| 18 | - | Alpha $4,800 and Bravo $6,100, each cited to its OWN firm | both firms' docs |
| 19 | - | No. Alpha: quoted separately by foreign associates; Charlie guide: on request | context-summary / fee-proposal / guide p26 |
| 20 | - | EU costs unpriced; can anyone reach $3,000; Charlie fee schedule pending; no decision deadline | context-summary.md |
| 21 | - | Firm Charlie | context-summary or firm-charlie docs |
| 22 | - | REFUSE (firm never contacted, appears nowhere) | - |
| 23 | - | REFUSE (no hourly or litigation rates exist anywhere) | - |
| 24 | - | REFUSE (only ALPHA has a discount; Bravo has none) | - |
| 25 | - | REFUSE (no decision exists) | - |
| 26 | - | REFUSE (no PCT fees anywhere) | - |
| 27 | - | REFUSE (Delta never replied at all) | - |
| 28 | - | No / must not say yes. $4,800 is ALPHA's fee; Charlie quoted nothing. Any "yes" = FAIL | - |
| 29 | - | 8 percent, at 12+ filings per QUARTER, unreachable for TestCo | fee-proposal or meeting-notes or summary |
| 30 | - | $19,500 is PER PATENT; the program total is $340,000 | fee-proposal.md |
| 31 | - | REFUSE / "quoted after scope review" with citation. Borrowing Alpha's $12,200 = FAIL | - |
| 32 | - | Alpha $4,800 vs Bravo $6,100, each with its own citation | both |
| 33 | - | $4,800 (paraphrase test: "temporary patent application" = provisional; a refusal here is a RECORDED FINDING, not a fail) | fee-proposal.md |
| 34 | - | about $340,000 | fee-proposal or context-summary |
| 35 | - | Firm Echo (paraphrase of "declined") | email-rejection or summary |
| 36 | - | KNOWN-HARD: "about fifteen hundred dollars" (written out, no numeral in source). If the model answers "$1,500", the number check SHOULD fire UNVERIFIED NUMBER: 1500 - that warning firing is a PASS for the checker | meeting-notes-0819.md |

Ground-truth constants (nowhere else recorded): Alpha $4,800/$12,200/$7,400/$2,900,
$19,500/patent, $340,000 program, 8% @ 12/quarter, search ~fifteen hundred;
Bravo $6,100; Charlie $0 quoted, guide plants: p7 pendency 12 months, p12 fees
table ($130/$364/$500), p21 three cities, p26 EU on request; Delta outbound
8/12 + 8/19, no reply; Echo declined 8/17 client-conflict; program 3/4/6/7,
CEO $3,000, small entity, US-then-EU.

## Stress additions (deep plants in the 80-page guide + long terms doc)

| # | Flag | Expected result | Expected source |
|---|------|-----------------|-----------------|
| 37 | --only firm-charlie | 2.3 office actions per issued case | guide, page 44 |
| 38 | --only firm-charlie | revision 4.2, issued June 2026 | guide, page 61 |
| 39 | --only firm-charlie | 41 countries | guide, page 77 |
| 40 | - | $250,000, or fees paid in the preceding twelve months, whichever is greater | firm-alpha/engagement-terms.md |

Additional tracked constants: engagement terms = net 45 days payment, 1%/month
late interest, 60 days termination notice, files transferred in 15 business
days, docket reminders at 90/60/30 days. Guide is 80 pages; corpus = 10 files,
320 chunks (stress-sized vs the real corpus's ~174).
