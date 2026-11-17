# Bobby Hedgefund

A paper-money biotech fund run by a team of LLM agents, fed by open data (clinical trials, FDA, SEC filings, papers,
company news), run forward for 26 weeks and compared with XBI, IBB, IWDA and two funds without AI (docs/SPEC.md).

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

## Next step
The plan is docs/SPEC.md ("Order of work"). In short:
1. Owner reads and merges the spec. Then Claude writes the decision records it lists (section 10), starting with
   0003-0008: how the agents run, the decision log, the paper funds, the universe and linking table, prices, SEC access.
2. Build data streams 0-3 on top of the archive: the linking table (with the owner's one-time check of about 200
   matches), daily prices, SEC filings, trial-record changes. Each starts with reading the source's terms.
   Alongside: the historical study, limited to two weeks of work. Open before it: AACT shows no terms page, so ask
   AACT before building that download.
3. Agent files, decision log and fund books; then the one-week pilot with one fund, which measures how much of the
   usage limits a session takes.
4. Streams 4-5, the scoring rules, the owner's go; the funds start for 26 weeks. Aim: pilot in January 2027, start
   in February 2027.
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
```

The nightly job runs an installed snapshot of the program, not this folder. After changing the archive code (merged
and tested), install the new version:

```
cd ~/projects/bobby-hedgefund
uv run ruff check && uv run ruff format --check && uv run pyright && uv run pytest
systemd/install.sh                 # installs the snapshot and the timer; refuses uncommitted or failing code
```

## Track record
None yet: the funds have not started. The plan is to publish it in this repository: every decision of every fund with
its reasoning and time, the value of each paper portfolio next to its benchmarks, and a regular plain-language report.
Published decisions are never edited afterwards. That nothing is added with hindsight follows from fixed rules
(docs/SPEC.md, section 2): a decision is public before the price it gets exists, and published history cannot be rewritten.
The record will be built from real market and trial data; the data files themselves are not published (see below),
only our own numbers and conclusions, with the sources named. The form is set in docs/SPEC.md, section 5: a folder
`track-record/` with the decision log, a readable page per day, the values per fund, and a monthly letter.

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

Sources that were only read for the research are linked where they are used in `docs/research/`. Candidates for later
streams, with their terms: docs/research/DATA-SOURCES.md.

## Licence
Code: MIT (`LICENSE`). Reports, decision records and results (`docs/`, this README): Creative Commons Attribution 4.0
(`LICENSE-CC-BY-4.0`). Why: docs/decisions/0002-licences-mit-and-cc-by.md. Files from the data sources are not part
of this repository and keep their own terms.
