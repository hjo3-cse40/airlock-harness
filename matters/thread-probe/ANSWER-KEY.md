# Answer key: thread-probe (49 questions)

PASS = the answer contains the expected facts (numbers and dates exactly as written in the
message) and cites thread.eml. REFUSE = the honest answer is that the thread does not say.
Summary questions pass when at least `min_facts` of the listed key points appear.
`eval_thread_probe.py` scores a batch run against `answer-key.json` deterministically.

| # | Type | Category | Question | Expected |
|---|---|---|---|---|
| 1 | fact | date_who | what day did he reply to the proposal? | Daniel replied on Thursday, May 7, 2026. |
| 2 | fact | date_who | who replied to Maya's proposal, and when? | Daniel Okonkwo, the Executive Director, replied on May 7, 2026. |
| 3 | fact | date_who | when was the proposal sent? | Maya sent the proposal on Monday, May 4, 2026. |
| 4 | fact | date_who | when did Maya send her follow-up questions? | Maya's follow-up with three questions was sent on Friday, May 8, 2026. |
| 5 | fact | date_who | when was his last message in the thread, and what was it about? | Monday, May 11: his quick answers to Maya's three questions (deposit from the expansion account, compost limit only for in-ground plots, school start season left open) plus the shed moved to the east corner. |
| 6 | summary | summary | summarize Daniel's reply | Approves the expansion in principle with changes: cap lowered to $34,000; 24 plots and 14 cedar raised beds by the gate; compost max 35%; Hollis water line at $6,900 with a $1,600 deposit; small shed on skids yes, second shed no; greenhouse deferred until the permit; $475 city permit via Lena Whitfield; no paid crew leader; bakery pledge $3,200 plus 27% of June loaves; Alder Hollow program only with a signed principal's letter; three deadlines (May 15, 21, 29) and a meeting May 19 at 6:30 p.m. |
| 7 | summary | summary | what did he say in general about the plan? | He approves the expansion in principle but not as proposed: the cap drops to $34,000, the greenhouse waits for the permit, the second shed and the paid crew leader are rejected, the water line is the priority, the two-season rule applies to anything permanent, the bakery pledge sits outside the cap, the school program needs a signed letter, and he wants a revised budget, the Hollis contract, and the layout by May 15, 21, and 29. |
| 8 | summary | summary | what are the main points of his May 7 email? | Approval in principle with changes; cap $34,000; 24 plots and 14 raised beds; Hollis water line $6,900 with $1,600 deposit; shed yes, second shed no; greenhouse deferred; permit $475 through Lena Whitfield; no paid crew leader; bakery $3,200 and 27%; Alder Hollow needs a signed letter; deadlines May 15, 21, 29; meeting May 19 at 6:30 p.m. |
| 9 | summary | summary | give me an overview of where things stand after the whole thread | Expansion approved in principle under a $34,000 cap; greenhouse deferred until the permit; Hollis water line approved with a $1,600 deposit paid from the expansion account; compost limit applies to in-ground plots only (raised beds may be half compost); shed moved to the east corner by the gate because the north line is in the setback; Alder Hollow start season still open until Daniel meets the principal; meeting May 19 at 6:30 p.m. |
| 10 | fact | specific_fact | what budget cap did he set? | Daniel lowered the cap to $34,000 (from Maya's proposed $41,250). |
| 11 | fact | specific_fact | what's the max compost share he'll allow in the fill mix? | No more than 35% compost for the in-ground plots, the rest screened topsoil; in his May 11 reply he adds that raised beds may go up to half compost. |
| 12 | fact | specific_fact | what percent of each garden loaf will Miller's Bakery give us? | 27% of the price of every garden loaf sold in June. |
| 13 | fact | specific_fact | how many in-ground plots did he approve? | 24 in-ground plots. |
| 14 | fact | specific_fact | how many raised beds did he approve, and where do they go? | 14 cedar raised beds, placed nearest the gate. |
| 15 | fact | specific_fact | how many active volunteers are on the spring roster? | 46 active volunteers. |
| 16 | fact | specific_fact | when can Hollis do the trenching? | Hollis can trench from June 16 to July 10. |
| 17 | fact | specific_fact | who's our contact at the city for the permit? | Lena Whitfield, the permits clerk at the city building office. |
| 18 | fact | specific_fact | how much is the city permit fee? | $475, paid to the city when the full application is filed, and not refunded if the permit is denied. |
| 19 | fact | specific_fact | what deposit does Hollis want before they schedule the trench? | A $1,600 deposit, which Daniel approved; the balance is due only after the city inspector signs off on the open trench. |
| 20 | fact | specific_fact | when and where is the meeting? | Tuesday, May 19 at 6:30 p.m. in the garden office. |
| 21 | fact | specific_fact | how much did the bakery pledge? | Miller's Bakery pledged $3,200 toward the expansion (plus 27% of June garden loaf sales). |
| 22 | list | decision | what did he reject, and why? | The second, larger shed (the old shed is a short walk away and it would pay for storage of things they do not own) and the paid weekend crew leader (paying one volunteer changes how every other volunteer sees the work, it cannot easily be stopped, and there is no room under the cap). |
| 23 | list | decision | what is he holding off on, and what is he waiting for before he decides? | The greenhouse (he will decide after the permit comes back from the city) and a sign with the bakery's name (he will decide after Priya reviews the partnership letter). |
| 24 | fact | decision | which program did he approve only on a condition, and what's the condition? | The Alder Hollow Elementary school program, provided the school sends a signed letter from its principal naming the supervising adults and confirming visits end before the afternoon heat. |
| 25 | fact | decision | did he approve the greenhouse? | Not this season; he deferred it and will decide after the permit comes back. The $9,750 stays in the plan as a line for next year, above the cap. |
| 26 | fact | decision | did he say yes to the second shed? | No. He approved only one shed on skids at $1,380 and rejected the second, larger shed. |
| 27 | fact | decision | why did he say no to the paid weekend crew leader? | Paying one volunteer changes how every other volunteer sees the work, once started it cannot easily stop, and there is no room for it under the cap; he would rather rotate row captains. |
| 28 | list | request_deadline | what does he want me to do and by when? | Revised one-page budget at or under the cap by Friday, May 15; Hollis contract with the deposit and inspection clause by Thursday, May 21; plot layout and row captain list by Friday, May 29. |
| 29 | list | request_deadline | list the three things he asked me to send him, each with its due date | 1. Revised budget, May 15. 2. Hollis contract with deposit and inspection clause, May 21. 3. Plot layout and row captain list, May 29. |
| 30 | fact | request_deadline | when does he need the revised budget, and what should it look like? | By Friday, May 15: a one-page budget at or under the $34,000 cap, keeping the same line items so Priya can compare side by side. |
| 31 | fact | request_deadline | by when does he want the Hollis contract, and what has to be written into it? | By Thursday, May 21, with the $1,600 deposit and the inspection clause (balance due only after the city inspector signs off) written in. |
| 32 | refuse | absence | does he say anything about parking? | REFUSE |
| 33 | refuse | absence | what did he decide about insurance for the new lot? | REFUSE |
| 34 | refuse | absence | did they discuss solar panels for the greenhouse? | REFUSE |
| 35 | refuse | absence | what did Priya reply? | Priya did not write any message in the thread; she was only cc'd on Daniel's May 7 reply. Daniel reports her view secondhand. |
| 36 | list | attribution | what did Maya ask in her follow-up? | 1. Should the $1,600 Hollis deposit come from the general account or the expansion account? 2. Does the 35% compost limit apply to raised beds too? 3. Should the Alder Hollow program start in June or wait until fall? |
| 37 | list | attribution | what did Daniel answer in his second reply? | Deposit comes from the expansion account (Priya writes the check when the countersigned contract arrives); the compost limit applies only to in-ground plots, raised beds can be up to half compost; the program start stays open until he walks the lot with the Alder Hollow principal; and the shed moves to the east corner by the gate because the north line is in the setback. |
| 38 | fact | attribution | which of Maya's three questions did he not really answer? | The third one, whether the Alder Hollow program starts in June or the fall; he deferred it until he has walked the lot with the principal. |
| 39 | list | attribution | list the items Daniel deferred in his May 7 reply | 1. The greenhouse (decide after the permit comes back). 2. The sign with the bakery's name (decide after Priya reviews the partnership letter). |
| 40 | fact | clarification | what does he mean by 'the two-season rule'? | Nothing permanent (anything with a footing, pad, or foundation that cannot be moved by truck and volunteers) gets built on the new lot until it has been gardened through two full seasons, one spring and one fall. |
| 41 | fact | clarification | what does Priya think about the plan? | As Daniel reports it: the water line is the one item that cannot be cut, and the bakery money is a pledge, not cash in the bank, so the cap does not assume it. |
| 42 | fact | change | what did he change between his first reply and his second one? | The shed location: he first said the north fence, then moved it to the east corner by the gate because Lena said the north line is inside the city's setback. |
| 43 | fact | change | what budget number did he change from Maya's plan, and to what? | The total budget: Maya proposed $41,250 and he lowered the cap to $34,000. |
| 44 | fact | trap | what does his reply say the soil delivery will cost? | $2,850, the quote from last year's yard, delivered and dumped in one load. |
| 45 | refuse | trap | what dimensions does he give for each in-ground plot? | REFUSE |
| 46 | fact | clarification | what did he mean by 'the cap is a ceiling, not a target'? | If the water line and beds come in under the cap, the difference stays in the general fund; it is not spent on extras. |
| 47 | fact | clarification | what did he mean when he said the bakery money is a pledge, not cash in the bank? | The pledge is not counted inside the $34,000 cap; it is treated as an addition when it arrives. |
| 48 | list | request_deadline | what questions did he ask me? | Four: fence ownership on the east line; how many beds at wheelchair height; the Alder Hollow contact and whether they saw the lot; whether anyone walked the lot after heavy rain. |
| 49 | fact | decision | did he say yes to hiring Hollis? | Yes: he approves the $6,900 Hollis quote and the $1,600 deposit; the balance only after the city inspection sign-off, written into the contract. |
