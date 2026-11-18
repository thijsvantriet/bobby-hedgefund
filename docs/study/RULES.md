# The historical study: rules, written down before any outcome is looked at

Date: 2026-11-18. Status: **proposed** (drafted by Claude; nothing is downloaded or analysed until the owner says yes).
Why this document exists: `docs/SPEC.md`, section 6 ("The historical study") and `docs/research/CASE-FORENSICS.md`,
section 7. The spec limits the study to **two weeks of work**.

**The study never scores the agents.** The models already know how past cases ended. It only delivers two kinds of
plain numbers that the forward experiment needs before the funds start.

## 1. What it must deliver
1. **Base rates:** how often a late-stage trial of a small or mid-size listed biotech company met its main goal.
   Used as the yardstick for the agents' forecasts (spec, section 4, "Quality of the probabilities") and for the
   exact rules of the Rules fund (record 0010).
2. **Typical size of the price move** on the day the result came out, apart for good and bad results and for small
   and larger companies. Used for "what is already priced in", for the make-or-break limit of the funds and for the
   20% alert threshold.

Nothing else. No trading rule is tested, and no signal is searched for.

## 2. What limits the study, stated up front
- **Prices go back two years only** (record 0007: the free plan). So the study period is fixed by the price files:
  results announced between **1 January 2025 and 30 September 2026**. That is short: expect 150 to 300 results.
  The numbers will be rough, and the report must say so with every figure.
- **Companies that disappeared are partly missing.** Our company list starts from the SEC's file of companies that
  are listed *today*. A company that went bankrupt or was taken over in 2025 is not in it, and such companies
  more often had bad results. The base rate will therefore look somewhat too good. We do not repair this in two
  weeks; the report states it, and counts how many tickers that traded in the first price files are no longer
  in the last ones.
- **No open list of past results exists** (`docs/research/OPEN-SOURCE.md`, "calendar"). The list is built by us,
  by the rule of section 3, not from memory and not from news lists.

## 3. Which results are in the study (the complete list)
A result is in the study when all of these hold. The list is made by script and frozen, with its fingerprint written
into this document, **before** any outcome or price is read.
1. The trial is in the dated copy of the registry (AACT) of **December 2024**, so the list rests on what was
   public before the study period.
2. It is a drug trial (interventional), phase 2/3 or phase 3, with a company as lead sponsor.
3. That sponsor name is linked to a company by the owner's checked linking table (record 0006), and the company
   passed the universe filter's size bounds on 31 December 2024 (market value from the price file of that day and
   the share count reported before it).
4. The registry gave a primary completion date between 1 October 2024 and 30 June 2026 (results usually follow the
   last patient visit by one to six months).
5. The company announced the main result in an SEC event report (8-K) inside the study period. Trials without
   an announcement in the period are counted and listed as "no result announced"; they are not dropped silently.

Phase 2 trials and FDA decision dates are **left out** of this first study: phase 2 has no single "met its goal"
standard, and FDA dates have no open source. Either can be a follow-up, with its own rules.

## 4. What is recorded per result, and by whom
| Field | Source | Who |
|---|---|---|
| Day and time of the announcement | The SEC's acceptance time of the 8-K | Script |
| Main goal met: yes / no / mixed or unclear | The press release attached to that 8-K, first paragraph and the sentence on the primary endpoint | A model reads only that document; see below |
| Phase, disease area, number of patients | The December 2024 registry copy | Script |
| Company size band on the day before | Price file and share count | Script |
| Price move | Section 5 | Script |

**Labelling the outcome.** A model (Opus) gets the press release only, with the instruction to answer from the text
and to quote the sentence it relied on. "Met" needs a stated statistically significant result on the primary
endpoint; a release that leads with a secondary endpoint or a subgroup is "mixed or unclear". The owner checks a
random 30 by hand; if more than 3 of 30 are wrong, all labels are redone by hand rules before any number is
reported. The labelling is finished and frozen **before** prices are joined to it.

## 5. The measures, fixed now
1. **Base rate** = results labelled "met" / all results with a label, for phase 3 and phase 2/3 together and apart.
   "Mixed or unclear" is reported as its own share, and the rate is shown twice: counting it as not met, and
   leaving it out. Next to it: the published figures (Wong, Siah and Lo 2019; BIO 2011-2020).
2. **Move on the day** = the share's return from the last close before the announcement to the first close after
   it, minus the return of XBI over the same days. Reported as the middle value and the quarter points, apart
   for "met" and "not met", and apart for companies under and over $1 billion.
3. **Run-up** = the same measure over the 30 trading days before the announcement.
4. **How often a move was "make-or-break"**: the share of results with a move beyond +100% or -50%.

No other cut of the data is reported as a finding. Anything else that is looked at is labelled "exploration" and
is not used to set a rule. Because the period is short, **nothing is held back as a second check**; the forward
experiment is the check.

## 6. Data and downloads
- **AACT** (record 0014, already settled): the monthly copies of December 2024 (the list) and of each month in
  the study period where a registry edit must be dated. **Proposed: start with one copy, December 2024**
  (about 2.6 GB). The base rates and move sizes need no other copy. More copies are fetched only if the owner asks
  for the registry-edit question to be looked at in history too.
  One download at a time, at night; credit to the Clinical Trials Transformation Initiative and ClinicalTrials.gov.
- **SEC:** the 8-K filings of the companies on the list for the study period. A by-hand job under the rules of
  record 0008 (one request a second), a few thousand requests in all.
- **Prices:** already stored. Nothing from them is published: the public report gives base rates (not computed
  from prices) and says only that move sizes were measured; the move figures themselves stay in a private
  appendix (record 0007).

## 7. Time box and stop rule
Two weeks of work, counted in sessions: at most **six sessions**. Order: (1) the list, frozen; (2) the filings;
(3) the labels, frozen, with the owner's check of 30; (4) the measures; (5) the report. If the list of step 1
holds fewer than 80 results, the study stops there and the base rates come from the published tables alone.
What fails or disappoints is published too.

## 8. For the owner to decide
1. **Go ahead on these rules?** (yes / change / drop the study and use the published tables only.)
2. **AACT:** start with the single December 2024 copy, as proposed, or fetch all months of the period
   (about 25 copies, 65 GB: fits on the disk, but is a lot to back up every night)?
3. **The check of 30 labels** is about half an hour of your time. Fine?
4. **The move figures stay private** (they are computed from prices). The public report then holds the base rates
   and the method only. Fine?
