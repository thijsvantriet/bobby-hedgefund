# Bobby Hedgefund

A paper-money biotech fund run by a team of LLM agents, fed by open data (clinical trials, FDA, SEC filings, papers,
company news), run forward for 26 weeks and compared with two funds without AI and with index funds (XBI, IBB and
a world index fund; docs/SPEC.md).

**This is an experiment with paper money. Nothing here is investment advice, and no real money is traded.**

**How far it is (2026-11):** only the research reports and the nightly data archive exist. There are no agents, no
portfolio and no results yet. The log below shows each step.

## Status
2026-11-15: project named Bobby Hedgefund (repo and folder `bobby-hedgefund`, renamed from biotech-agents). Idea brainstormed with Claude (see docs/IDEA.md, incl. a prior-art check). Project folder created; no spec, no code yet.

2026-11-15: overnight research done: what to reuse, which data to collect, and a first look at past cases. Start with docs/research/SUMMARY.md; it ends with the open questions for the spec interview. No code, nothing installed.

2026-11-16: owner's answers to the four start questions recorded in docs/research/SUMMARY.md (SEC contact address, public-repository rule, free sign-ups, start the archive now). **Day-1 archive built**: a nightly job that only saves public files their publishers overwrite. See "Day-1 archive" below and docs/decisions/0001. First runs done the same day: the one-time full copy of 170,083 company-linked trial records (444 MB) is stored and the whole archive passes its check. Known issue: the EMA site refuses one of its five files now and then, so an occasional "Bobby archive" phone message about EMA is expected.

2026-11-16: owner created the free accounts; keys are in the local `.env` (never in git). Eight of nine tested and working (Tiingo, Massive, openFDA, FRED, NCBI, FDA Data Dashboard, OpenAlex, AACT); EPO waits for approval. AACT's key turned out to give dated full copies of the registry, monthly back to 2017: the base for the historical study (details in docs/ACCOUNTS.md).

2026-11-16: research and archive merged into `main` after a second review of the archive code (one serious finding, fixed: a run now refuses to write when the list of stored files has lost its newest lines). The nightly job runs the version installed from `main`; 76 tests pass.

2026-11-16: preparing to make the repository public. A private e-mail address was removed from the history, and the GitHub repository was created anew from the clean history (so the first three pull requests no longer exist). Licences chosen: MIT for code, CC BY 4.0 for reports and results (docs/decisions/0002). Still private; left to do before opening: the owner reads the files once for details about the home setup.

2026-11-16: read-through done (all files, the whole history, the research reports). A few details about the home setup and a few statements about named people were reworded; no key, address or source data was found. Added: "Track record" and "Data sources and credit" below. The terms of ClinicalTrials.gov and Nasdaq were read (docs/decisions/0001, "Update"). Merged into `main` (PR #2), nightly job reinstalled from it. **Repository still private: it is made public only after the owner says yes in so many words**; then check from outside that it is public, the licence shows, and no old pull request or private address can be reached.

2026-11-16: **the repository is public** (owner's explicit yes). Checked from outside without a login: it is visible, GitHub shows the MIT licence, description and topics, only the four pull requests of the new repository exist, the commits of the old repository are not found, and every commit carries GitHub's no-reply address.

2026-11-17: EPO approved the account; its key works. All nine free accounts are now set up (docs/ACCOUNTS.md). The owner confirmed the ClinicalTrials.gov terms from the live page (docs/decisions/0001, "Update").

2026-11-17: EMA refused one of its five files on every run so far. Changed: a refused file is left alone and tried again after 10, 20, 40 and 60 minutes, instead of three quick retries (docs/decisions/0001, "Update 2026-11-17"). To check after a week of nightly runs.

2026-11-17: **spec drafted** (docs/SPEC.md, status "proposed" until the owner merges it). Claude drafted it from the research with one recommendation per choice; the owner decided eight points (session length, days a week, share of the usage limits, free data only, where the app lives, the letter, the alerts, when it ends). No code and no decision records yet. Later the same day the owner simplified the daily routine: their only action is typing `/bobbyhedgefund-day`, each day's round starts in a fresh session, and the leak check, usage count and weekly/monthly extras run by themselves.

2026-11-17: **spec approved**: the owner merged PR #8. Next: Claude writes decision records 0003-0008.

2026-11-17: **decision records 0003-0008 written** (docs/decisions/, PR #10, all "proposed" until the owner merges them): how the agents run, the decision log, the paper funds, the universe and linking table, the price source, SEC access. Each rests on a narrow research question and on the source's own terms where a download is involved. Reading the terms changed three things from the spec: (1) Tiingo's free plan cannot be used at all, so Massive is the only price source, and no price, share count or index-fund series may be published (0007); the public log therefore "seals" such content: it shows a fingerprint, not the number (0004); (2) SEC filings are fetched by our own small program and only read with the edgartools library, and the SEC's "latest filings" feed is off limits to scripts (0008); (3) companies that report to the SEC as foreign companies are left out of version 1 (0006). Three open points wait for the owner: ask Massive in writing whether our own fund results may be public (0007), check that the Claude account does not use conversations for training (0007), and choose how to keep published company names from giving away holdings of the XBI fund (0006; nothing that names a company is published before that). Merging the records also confirms the places where they differ from the spec, listed in each record under "Differs from the spec" (among them: no foreign filers in version 1, our own program fetches SEC filings, the world index through the US-listed fund URTH, index comparisons private). A reviewer agent checked the records against the spec and each other; its findings are worked in. No code was written.

2026-11-17: **records 0003-0008 accepted**: the owner went through the main points and merged PR #10. Chosen on the way: two more industry codes (8731, 2835) as a door of our own, so that published company names do not point to the XBI fund (0006); the Claude account's training setting is confirmed off (0007); after the pilot week we review what the agents miss without web access (0003). The differences from the spec are listed in its "Changes" section.

2026-11-17: the owner asked Massive whether our own fund results may be public (weekly, rounded returns and the place among the random funds; no prices). **Answer the same day: no**, public display of anything derived from its data needs a business licence. So nothing computed from prices is published; fund results are kept privately and shown in the app at home, and the public track record shows decisions, reasoning, fill days and forecast scores (docs/decisions/0007, open point 1).

2026-11-17: **AACT download settled** (docs/decisions/0014). AACT shows no terms of use and its robots file forbids nothing; the owner decided that this counts as permission, so no question is sent. The record sets the download rules: only the monthly copies the study needs, each once, never published, CTTI credited. Nothing downloaded yet.

2026-11-18: **stream 0, part 1: SEC access built** (`bobby-archive sec-companies`, docs/decisions/0008, "Update 2026-11-18"). Before the first request the SEC's robots files were read: the data service has none, and the main site does not forbid the ticker file. The command stores the SEC's ticker file and the filing list of every company with a stock-exchange listing (6,051), one request a second, about two and a half hours, once. Tried on 20 companies first; the archive check passes and the contact address is stored nowhere. Stream 0 is built in five parts: (1) these SEC files, (2) the candidate list and the sponsor names, (3) daily prices, (4) the filter, (5) name matching and the owner's check. The universe filter needs prices, so the linking table comes after stream 1.

2026-11-18: **stream 0, part 2: candidate list and sponsor names built** (`bobby-universe`, see "Universe and linking table" below). Reading code only, on files the archive already holds; every file read is checked against its fingerprint. First result: 26,149 distinct company-like sponsor names in 170,192 trial records. A reviewer agent found that a look-alike ticker (AB-C next to ABC) could link a fund holding to the wrong company; fixed and tested before the merge. The candidate list is written once the SEC company files are complete; its counts (among them: how many companies come in through the XBI fund only) then go into docs/decisions/0006 as an update.

2026-11-18: **the owner wants the pilot at the end of November 2026**, not in January. The order of work stays; see "Next step" for what must exist by then.

## Next step
The plan is docs/SPEC.md ("Order of work"). In short:
1. ~~Owner reads and merges the spec~~ (done 2026-11-17). ~~Decision records 0003-0008~~ (accepted 2026-11-17).
   Records 0009-0014 follow when their step comes (spec, section 10).
2. **Now:** build data streams 0-3 on top of the archive: the linking table (with the owner's one-time check of about 200
   matches), daily prices, SEC filings, trial-record changes. The terms for prices and SEC filings are read
   (0007, 0008). Stream 0, parts 1 and 2 (the SEC company files, the candidate list and the sponsor
   names) are built; next is daily prices (stream 1, record 0007), then the filter and the name matching.
   Alongside: the historical study, limited to two weeks of work. Its AACT download is settled (0014): go ahead
   under the download rules written there; choose which monthly copies to fetch first (all of them do not fit on the disk).
3. Agent files, decision log and fund books; then the one-week pilot with one fund, which measures how much of the
   usage limits a session takes.
4. Streams 4-5, the scoring rules, the owner's go; the funds start for 26 weeks. No waiting for a date (owner, 2026-11-17): the pilot starts as soon as the setup is done, and the funds start right after the pilot and the owner's go. Target (owner, 2026-11-18): the pilot starts at the end of November 2026. Needed before it: streams 0-3, record 0009, the agent files, the decision log with its leak check, and the fund books.
5. In the first live weeks: the app, the alerts and the first monthly letter. A review with the owner every month.

## Day-1 archive
A job that runs every night at 23:30 and saves a few public files exactly as published, because their publishers
overwrite them. It does no analysis. What, where and why: docs/decisions/0001-day-1-archive-storage-and-backup.md.

- **Saved:** trial records with a company involved (ClinicalTrials.gov), five European Medicines Agency files, the
  Nasdaq symbol lists, and the daily holdings of the XBI fund.
- **Where:** `~/bobby-hedgefund-data/archive/` (never in git). The machine's nightly encrypted backup covers it.
- **If something fails:** a phone message "Bobby archive". Then:

```
bobby-archive status               # last run per source, stored size
bobby-archive verify               # re-reads every file and checks it against its fingerprint; writes nothing
                                   # (answers "busy" while a nightly run is still waiting to retry a file)
bobby-archive run                  # run the daily download by hand
bobby-archive baseline             # one-time full copy of the trial records (--resume if interrupted)
bobby-archive sec-companies        # monthly, by hand, during the day: SEC ticker file and filing lists (hours;
                                   # --limit N for a first try, --resume to continue; no new request after
                                   # 22:30, so the nightly run is never kept waiting)
```

The nightly job runs an installed snapshot of the program, not this folder. After changing the archive code (merged
and tested), install the new version:

```
cd ~/projects/bobby-hedgefund
uv run ruff check && uv run ruff format --check && uv run pyright && uv run pytest
systemd/install.sh                 # installs the snapshot and the timer; refuses uncommitted or failing code
```

## Universe and linking table (stream 0, in progress)
Design: docs/decisions/0006. Two commands read the archive and write dated files next to it; they download nothing
and never replace a file (a second run on one day gets `-2` in its name). The results are private: they hold the
XBI flag and are never committed.

```
bobby-universe candidates          # companies that can enter the universe, before the filter on size and trading
bobby-universe sponsor-names       # every company-like sponsor name in the archived trial records (2 minutes)
```

- `~/bobby-hedgefund-data/universe/<date>_candidates.csv`: one line per company with one of our four industry
  codes or a place in the XBI fund: SEC company number, name, tickers, industry code, the door it came through,
  whether it reports as a foreign company (left out of version 1), former names, a check of its ticker against
  the Nasdaq lists, and the name the fund's file gives it (the link to the fund is made by ticker, so the two names
  can be compared by eye). A fund holding that cannot be linked to exactly one company goes to
  `<date>_xbi-unmatched.csv` instead of being guessed. `<date>_inputs.txt` lists the archived files that were
  read, with their fingerprints.
- `~/bobby-hedgefund-data/linking/<date>_sponsor-names.csv`: sponsor name as written in the registry, its classes,
  number of trials, one example trial.
- In these files a text that a spreadsheet would run as a formula (starting with `=`, `+`, `-` or `@`) has an
  apostrophe in front.

Still to come: daily prices, the filter, name matching and the owner's check of the matches.

## Track record
None yet: the funds have not started. The plan is to publish it in this repository: every decision of every fund with
its reasoning and time, the day it was filled, the score of every forecast, and a regular plain-language report.
Fund values, returns and comparisons with index funds are not published: the price service's terms do not allow
public display of anything computed from its prices (docs/decisions/0007). They are kept privately.
Published decisions are never edited afterwards. That nothing is added with hindsight follows from fixed rules
(docs/SPEC.md, section 2): a decision is public before the price it gets exists, and published history cannot be rewritten.
The record will be built from real market and trial data; the data files themselves are not published (see below),
only our own numbers and conclusions, with the sources named. The form is set in docs/SPEC.md, section 5: a folder
`track-record/` with the decision log, a readable page per day, the forecasts and a monthly letter.

## Data sources and credit
The project follows each source's terms of use. No file from any source is in this repository, and none will be:
published results show only our own analysis, with the source named. This project is not affiliated with or endorsed
by any of them. Downloaded so far (details and terms per source: docs/decisions/0001):

| Source | What we save | Condition we follow |
|---|---|---|
| [ClinicalTrials.gov](https://clinicaltrials.gov/) (U.S. National Library of Medicine) | Trial records with a company involved | Free for everyone. In anything published from it: credit ClinicalTrials.gov as the source, keep it current, show the date the data were processed, and describe any change made to the data ([terms](https://clinicaltrials.gov/about-site/terms-conditions)). We send at most one request per two seconds |
| [European Medicines Agency](https://www.ema.europa.eu/en/about-us/about-website/download-website-data-json-data-format) | Five data files on medicines | Reuse allowed with the source credited ([legal notice](https://www.ema.europa.eu/en/about-us/about-website/legal-notice)) |
| [Nasdaq Trader symbol directory](https://www.nasdaqtrader.com/Trader.aspx?id=SymbolDirDefs) | Lists of US-listed symbols | Copyright Nasdaq, Inc. One copy for personal, non-commercial use; the files are never passed on or published ([terms](https://www.nasdaqtrader.com/Trader.aspx?id=CopyDisclaimMain)) |
| [State Street, SPDR S&P Biotech ETF (XBI)](https://www.ssga.com/) | The fund's daily holdings file | Personal use only; the file is never passed on or published ([terms](https://www.ssga.com/us/en/intermediary/footer/terms-and-conditions)) |
| [U.S. Securities and Exchange Commission, EDGAR](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) | The ticker file and each listed company's filing list (from 2026-11-18) | Free for everyone; at most one request a second with a declared contact, as the SEC asks; the filings' own text belongs to the companies and is only summarised and linked, never republished at length (docs/decisions/0008) |

Sources that were only read for the research are linked where they are used in `docs/research/`. Candidates for later
streams, with their terms: docs/research/DATA-SOURCES.md.

## Licence
Code: MIT (`LICENSE`). Reports, decision records and results (`docs/`, this README): Creative Commons Attribution 4.0
(`LICENSE-CC-BY-4.0`). Why: docs/decisions/0002-licences-mit-and-cc-by.md. Files from the data sources are not part
of this repository and keep their own terms.
