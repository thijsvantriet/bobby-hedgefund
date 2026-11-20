# 0006. Universe and linking table: sources, filter, and how matches are stored and checked
Date: 2026-11-17
Status: accepted (owner, 2026-11-17: read the main points and said "merge"). The open point on the XBI names is settled: option a.

## Context
Two lists carry everything else (`docs/SPEC.md`, section 4 "Universe" and section 6, stream 0):
- the **universe**: the 150-250 companies the funds may follow;
- the **linking table**: which company belongs to which SEC number, ticker, sponsor names in the trial registry, and
  later which drugs and trials.

The spec fixed who is in the universe (companies in the XBI fund plus US-listed SEC filers with industry codes 2834
and 2836), the filter (market value $300 million to $10 billion, at least $2 million traded a day, share price at
least $2), that it is frozen with a date and re-run monthly with every version kept, and that the owner checks about
200 matches once. Left to this record: where each field comes from, how names are matched, and how the lists are
stored so that it can always be shown which version a session used.

A wrong link is costly: news of one company would be read as news of another. And no open list links trial sponsors
to listed companies (`docs/research/OPEN-SOURCE.md`, "Linking the data"; confirmed again: the published studies of
registry sponsors leave name variants unmerged, and say that automatic matching is less accurate than matching by
hand).

Requirements: free and official sources; one permanent key per company; nothing overwritten; the XBI holdings file
and the Nasdaq lists are never passed on (`docs/decisions/0001`).

## Options considered

**Storage of the lists**

| Option | How it works | For | Against |
|---|---|---|---|
| **A. Dated plain files** | Every run writes a new dated file (CSV). The owner's accept/reject decisions go into a file that only grows. Nothing is overwritten. | Readable in any spreadsheet; two versions can be compared line by line; the same pattern as the archive; a session notes the file's name and fingerprint. Matches the published advice for research data: keep raw data, use plain formats, give every record a permanent key | A question across many versions needs a small script |
| B. A database with "valid from / valid to" dates per row | One file (SQLite); a change adds a row and closes the old one. The standard method in data warehouses | Easy to query | One file that changes every month: a bug can rewrite history unnoticed; harder to check by eye |
| C. A, plus a database rebuilt from the files | Files are the truth, the database is a copy for searching | Both | More code; not needed for a few hundred rows |

**Matching company names to sponsor names**

| Option | For | Against |
|---|---|---|
| Exact names only | No false matches | Misses most: registry names are free text ("X Therapeutics, Inc.", "X Tx", a subsidiary) |
| **Similarity scores, every suggested match confirmed by a person** | Standard practice in record linkage: clean the names, score how alike they are, let a person judge the doubtful ones, report how many were right and how many were missed | The owner's time, once |
| A statistical or learned matcher (splink, dedupe) | Scales to millions | Far more than one name field and 200 companies need; harder to explain |

## Decision

### 1. One key
Every row is keyed on the **SEC company number (CIK)**. The SEC states that these numbers are never reused. Tickers
change and get reused, so a ticker is a property with a date, never a key.

### 2. Where each field comes from

"Shell company" below means a listed company without a real business, often waiting to merge with one.

| Field | Source | Known limit |
|---|---|---|
| Company number, name, former names, industry code | SEC, each company's filing-list file (access rules: record 0008) | Companies choose their own industry code and rarely update it |
| Ticker and exchange | SEC's company-ticker-exchange file; the Nasdaq symbol lists in the archive as a check | The SEC says of this file that it does "not guarantee accuracy or scope"; it shows today's tickers only, so we keep a copy per run |
| In the XBI fund | The daily holdings file already in the archive | Private: never published, see point 6 |
| Shares outstanding | The figure on the cover page of the latest quarterly or yearly report, from the SEC's data service | Up to a quarter old, older after a share sale; companies with several share classes report each class apart |
| Price, daily traded value | The price source (record 0007) | See there |

**The filter, made exact:**
- market value = shares outstanding (all classes added up) × the last closing price;
- traded per day = the average of closing price × volume over the last 60 trading days;
- share price = the last closing price;
- listed on Nasdaq, the New York Stock Exchange or NYSE American; not flagged as a shell company.

Every company gets a line with the numbers used and their dates, also the ones that fail the filter, so that the
effect of each rule can be seen.

OpenFIGI (a lookup service for security identifiers, run by Bloomberg; the identifiers are free, the service is
closed) is **left out**: the SEC's own files are enough for US shares.

### 3. Matching, step by step
1. Per company: the SEC name and all former names; lower case, punctuation and legal endings (Inc, Corp, Ltd, plc)
   removed. The original text is kept next to the cleaned one.
2. From the archived trial records: every distinct name of a lead sponsor or collaborator that the registry classes
   as industry, or as unclear. Cleaned the same way.
3. Every company name is scored against every sponsor name with the open-source library rapidfuzz (MIT). A name that
   is identical after cleaning is marked "strong".
4. **Review file for the owner:** a spreadsheet file with one line per suggested match: company, sponsor name as
   written in the registry, score, number of trials, one example trial, and two empty columns: decision (yes, no,
   parent or subsidiary) and note. **Nothing is accepted automatically in version 1**, not even the strong ones.
5. **Check for missed matches:** for 20 companies picked at random, the registry is searched by hand, and what step
   3 missed is counted. The share of right suggestions and the share of missed ones are added to this record as an
   update.
6. **Monthly re-run:** only new companies and new sponsor names go to the owner. Earlier decisions are reused and
   never edited; a changed mind is a new line that points to the old one.
7. **Trials, then drugs.** A company's trials follow from its confirmed sponsor names. Trials run by a partner are
   found through drug names; these are added in a later step, each with the document they came from, and are checked
   on a sample. Until then the table says plainly that partner trials can be missing.

### 4. Storage: option A
```
~/bobby-hedgefund-data/universe/
  2027-01-05_universe.csv        every candidate, the numbers used, in or out, and why (private: has the XBI flag)
  2027-01-05_inputs.txt          which archived files and price files this run read, with their fingerprints
~/bobby-hedgefund-data/linking/
  decisions.jsonl                the owner's decisions, one per line, only ever added to
  2027-01-05_linking.csv         the table as it follows from the decisions on that date
```
The session's start record in the decision log names the universe file it used and its fingerprint (spec, section
5). A database copy for searching (option C) may be added later; it would be rebuilt from these files and never be
the source.

### 5. When
The first version is made before the pilot; the owner's check happens then. The re-run is on the first session of
each month, after publishing (spec, section 1). It uses only files that the nightly jobs saved.

### 6. What is published
The universe is meant to be published in `track-record/` as **our own list**: company name, SEC company number
and ticker, with the date of the version. The ticker is taken from the SEC's file and used only as a name; the
Nasdaq lists are a private check. No column says how a company got in, and the XBI holdings file is never
published. The public page credits the SEC, and ClinicalTrials.gov with the date its records were processed, as
their terms ask (`docs/decisions/0001`). The review file and the linking files stay in the data folder.

The open point below was settled on 2026-11-17 (option a), so the list and records that name a company may be
published once the first run has shown that no company comes in through the XBI fund only, or those companies are
left out of what is public (record 0004, point 3).

The private universe files hold market values computed from prices, so they fall under the deletion rule of record
0007 if the price account ever ends. What stays in that case is the list of who was in and out, without the numbers.

## Differs from the spec
1. One narrowing, for the owner to confirm: **companies that report to the SEC as foreign companies are left out of
   version 1**, also when their shares trade in the US. They file no quarterly reports, no event reports in the
   usual form and no insider trades, so streams 2 and 4 would be empty for them, and their share count is published
   once a year. The spec already leaves out non-US listings; this goes one step further.
2. **Open point for the owner: the public list gives away part of the XBI fund's holdings.** The spec says that
   which companies are in the XBI fund is never published. But a company on our public list that does not have
   industry code 2834 or 2836 can only have come in through the XBI fund, and anyone can look up a company's code.
   The same holds for such a company named in a published decision. State Street's terms forbid passing its data
   on. Three ways out:

   | Way out | For | Against |
   |---|---|---|
   | **a. Add two more industry codes as a door of our own** (8731, research services, and 2835, diagnostics, where many young biotech companies sit), with the same filter | A company outside 2834 and 2836 then no longer points to the XBI fund. Also closes the known gap that such companies are missed | The universe changes a little; more companies that are not biotech must be marked out in the owner's review |
   | b. Drop the XBI fund as a door | Nothing can be inferred | Misses the biotech companies that carry yet another code |
   | c. Accept it | No change | Goes against the spec's own sentence, and arguably against the terms |

   **Decided by the owner on 2026-11-17: option a.** Companies with industry code 8731 or 2835 that pass the same
   filter are in the universe by our own rule. The first run counts how many companies still come in through the
   XBI fund only (with yet another code); if any do, they are not named publicly, and the count is added here as an
   update.

## Consequences
- It can always be shown which universe a session used, and why a company was in or out on that date.
- The owner checks roughly 200 companies' suggested matches once, and a handful every month.
- Known gaps, accepted: many young biotech companies carry another industry code (research services, diagnostics) and
  get in only through the XBI fund; code 2834 also holds makers of generic and over-the-counter medicines, which the
  size filter does not remove. The owner's review file shows them, and a company can be marked "not biotech" there.
- Market value can be off by the size of a recent share sale until the next report. The filter bounds are wide
  enough for that; a company near a bound may enter a month late.
- The universe needs 60 trading days of prices before its first version; record 0007 fetches that history once.
- Partner-run trials are missing until the drug-name step is built.

## Revisit
Later, maybe: a database copy for searching; OpenFIGI to tell share classes and foreign listings apart; foreign
filers in a version 2.

## Update 2026-11-18: how the filter and the matching are built
Commands: `bobby-archive sec-shares`, `bobby-universe build | match | decisions | linking | missed-check`
(README, "Universe and linking table"). What had to be settled while building, beyond the text above:

**Share count (point 2).** The SEC's data service is asked for two figures per candidate: the share count on the
cover page of a report, and the one on the balance sheet. The newer of the two is used. Limits found:
- The service only holds figures a company reports *for the company as a whole*. A company that reports each
  share class apart has neither figure and falls out with the reason "no share count reported for the company as
  a whole". These are listed for the owner; adding them by hand from the report is a later step.
- A count older than 15 months does not count (a yearly report plus the time allowed to file it).
- Several figures for one day in one report are added up, with a note (share classes).
- **Share splits.** A split after the report was *filed* changes the number of shares, so the count is multiplied
  by the split's ratio, with a note. A split between the day of the count and the filing day is **not** applied:
  companies must restate their share figures for such a split, so it is normally in the count already; the line
  gets "CHECK" in its note. The split list is the price service's (record 0007).
- The build refuses to run until the share counts of the current batch are complete, so "not fetched yet" can
  never look like "reports no share count".

**Which ticker.** A company can have several tickers (share classes, warrants, units, preferred shares), and the
SEC's file does not always list the common share first. The ticker with the most money traded over the 60 days is
used; all tickers with prices are shown. The SEC writes a share class with a dash, the price service with a dot;
only that difference is bridged, never a look-alike.

**The filter, two additions.** (1) A share without a price in the last 5 trading days is out ("no longer
trades"): a company taken over two months ago would otherwise pass on its old prices. (2) "Average over the last
60 trading days" counts a day without trading as zero, so a newly listed share can enter a month late.
"Shell company" is read from the SEC's industry code for blank-check companies (6770); the cover-page flag is
not fetched. In the SEC's ticker file "NYSE" also covers NYSE American.

**Cleaning names (point 3, step 1).** Beyond lower case, punctuation and legal endings: accents are removed;
"&" is read as "and"; the tags the SEC adds to many names are dropped ("/DE/", "/NEW", "/ADR"); "Holdings" and
"Group" count as endings.

**Kinds of suggestion (step 3).** Scoring every pair with one similarity score gave mostly noise: two names
that share a long word such as "Pharmaceuticals" score as alike. So a suggestion is one of five kinds:
- **strong**: identical after cleaning;
- **core**: identical once the words that only say "drug company" are left out (Therapeutics, Pharma,
  Biosciences, ...), for a core of at least four letters;
- **starts**: the sponsor name starts with the company's whole cleaned name (a subsidiary, a country branch);
- **contains**: the sponsor name holds the company's whole cleaned name further on ("X Bio, a wholly owned
  subsidiary of ..."), for a name of at least eight letters;
- **similar**: nearly the same spelling (rapidfuzz, 90 of 100), and the part that tells the company apart must
  be nearly the same too (85 of 100) or the first word identical.
Former names are tried as well. Strong and core suggestions are always shown; of the three weaker kinds at most 25
per company, most trials first, and the sheet says how many were left out.

**The review sheet (step 4).** A spreadsheet with a how-to page; one grey line per company and its suggestions
under it. On the company line the owner can choose "not biotech" (the known gap of code 2834: generics makers);
the next universe run then leaves that company out, and "biotech" takes the mark back. A read-only copy of the
sheet is kept; when the filled-in sheet is read back, every decided line must still be a line of that copy, and
one wrong line refuses the whole sheet, with the line numbers. Names can never run as a spreadsheet formula.

**Decisions (point 4).** `decisions.jsonl` is only ever added to, under a lock; every line carries the
fingerprint of the line before it, and a damaged file is refused, not continued. A changed decision is a new
line with the number and fingerprint of the line it replaces.

**A third share figure.** The first real run showed about ten mid-size companies falling out only because the
service has neither share count for them (they report per share class). So a third figure is fetched: the
average number of shares over the reported period, which nearly every company reports. It is used only when no
count on a day is usable, and the line says so. It is an approximation: an average over a quarter, not a count.

**First run, 2026-11-18** (counts only; the files are private):
- Candidates: 704 companies of 6,051 with a stock-exchange listing. 547 through an industry code of our own,
  150 through a code and the XBI fund, **7 through the XBI fund only**. 102 report as foreign companies and are
  left out; none has an unknown way of reporting. Of the fund's 159 holdings, 157 were linked to a company; the 2
  others are listed for a look by hand.
- Universe: **221 companies**, inside the 150-250 the spec expected. How many companies fail each rule on size,
  trading and price is in the private inputs file of the run, not here: those counts are computed from prices
  (record 0007). Not from prices: 102 foreign filers; 25 companies without a usable share count (3 of them fail
  on nothing else: young companies without a report yet); 19 companies run on the average figure; 7 lines carry
  the "CHECK" note for a split between the count and its filing, and all 7 fail the filter on other rules anyway.
- **XBI only (the open point of "Differs from the spec", 2):** 6 companies of the universe come in through the
  XBI fund only, with yet another industry code. As decided there, they are not named publicly: the published
  universe list and any published record must leave them out (record 0004, point 3) until the owner decides
  otherwise.
- Matching: 221 companies against 26,149 sponsor names gave 311 suggestions (228 strong, 22 core, 33 starts, 15
  contains, 13 similar; 71 through a former name). 15 companies have no suggestion at all. Some of those run
  no trials of their own (tools and services companies); for others the registry may class the sponsor as
  something other than "industry", and then their trials are not in our archive at all. The by-hand check of
  step 5 (`bobby-universe missed-check`) is the place to find out. The right and missed shares of step 5 are
  added here after the owner's check.

**Review.** A reviewer agent read the code before the pull request. Worked in, among others: the split rule
above (the first version would have counted a split twice for a balance-sheet count), the completeness check,
the ticker choice, the SEC's name tags, a stop when the share-count service answers "not found" many times in a
row (then the address is wrong, not the companies), and names with line breaks or control characters.

## Update 2026-11-20: who judges the review sheet

**What changed.** The record gave the whole review sheet to the owner. On opening it the owner pointed out that the
job asks for a judgement about 221 companies he does not know, so a yes from him would check nothing. From now on:
- Claude gathers the evidence for every line and decides the lines it is sure about. The evidence is what the
  archived trial records say about the sponsor name (its drugs, conditions, countries, years, and the lead sponsor
  where the name is a collaborator), compared with the company's names and former names from the SEC.
- The owner sees only the lines Claude is not sure about, each with a recommendation, and decides those.
- Every decision made this way carries a note that starts with "Claude" and the date, so it can be told apart later.
- The by-hand check of 20 companies for missed names stays as the safety net.

**Why this is acceptable.** A decision is never final: a changed mind is a new line that replaces the old one. A
wrong link shows up as trials that do not fit the company, which the analysts see.

**The cost.** A mistake by Claude in the lines it calls sure goes through without the owner seeing it.

**First run, 2026-11-20** (counts only). Of 311 suggestions, 281 were decided: 205 yes, 35 parent or subsidiary,
41 no. The linking table has 240 sponsor names for 204 companies and 4,537 trials. 30 lines wait for the owner:
- 26 are the former name of a stock-exchange shell that a new business merged into. The registry name is the same
  legal company, but its trials belong to the business before the merger. Recommendation: do not link them.
- 4 are cases where the company's recent history could not be confirmed from the files.

**The owner's answers, 2026-11-20.** The owner agreed with all recommendations. The 26 shell names got a no; the
4 uncertain lines were linked (3 as parent or subsidiary, 1 as yes). All 311 suggestions are now decided: 206 yes,
38 parent or subsidiary, 67 no. The linking table has 244 sponsor names for 204 companies and 4,703 trials.
The owner also marked 18 companies "not biotech": 2 that are not in health care at all, and 16 that have no
medicines of their own in trials (medical tests, lab supplies and services, food and animal products, drugstore
products, licensed technology). *Why:* their prices move on sales, not on trials and approvals, which is what the
analysts read. Generics makers and companies that live on income from other companies' drugs stay in. The universe
was built again the same day: 204 companies (221 before; 18 marked out, 1 came in through the filter and still
needs its sponsor names matched).

The former-name warning on the sheet proved its worth: two names that looked identical to a former name were in
fact a different, later company.

## Sources
- SEC, [Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
  (company numbers "are not recycled"; the ticker files; read 2026-11-17)
- ClinicalTrials.gov, [data fields of the service](https://clinicaltrials.gov/api/v2/studies/metadata) (lead sponsor,
  collaborators, sponsor class)
- Office for National Statistics (UK), [Developing standard tools for data linkage](https://www.ons.gov.uk/methodology/methodologicalpublications/generalmethodology/onsworkingpaperseries/developingstandardtoolsfordatalinkagefebruary2021)
  (cleaning, scoring, review by a person of the doubtful cases, reporting right and missed matches)
- Sponsor names in the registry are not standardised: [PLOS ONE 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC4757412/);
  automatic matching less accurate than by hand: [TrialsTracker](https://f1000research.com/articles/5-2629/v1)
- Wilson et al., [Good enough practices in scientific computing](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005510)
  (never overwrite raw data, plain formats, a permanent key per record)
- Kimball Group, [type 2 slowly changing dimension](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-2/) (option B)
- [rapidfuzz](https://pypi.org/project/rapidfuzz/) (MIT); [OpenFIGI terms](https://www.openfigi.com/docs/terms-of-service)
- Earlier research: `docs/research/OPEN-SOURCE.md` ("Linking the data"), `docs/research/DATA-SOURCES.md`
  ("Corporate actions and the universe")

Not verified: the SEC pages that describe the industry codes and the share-count figure were not fetched (their
limits above come from the earlier research and general knowledge, and are checked on the first run); whether the
registry assigns the sponsor class itself or takes it from the sponsor.
