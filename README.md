# Bobby Hedgefund

A paper-money biotech fund run by a team of LLM agents, fed by open data (clinical trials, FDA, SEC filings, papers,
earnings calls), run forward on the home server for about 6 months and compared with XBI, IBB, IWDA and real biotech funds (ARKG, 13F filers).

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

## Next step
1. Interview + spec (docs/SPEC.md), in plan mode. Agenda: the open questions in docs/research/SUMMARY.md.
   Terms: read on 2026-11-16, ClinicalTrials.gov confirmed by the owner in a browser on 2026-11-17
   (docs/decisions/0001, "Update"). Open: AACT shows no terms page, so ask AACT before building that download.
   Also for the spec: where and in what form the track record is published (see "Track record").
   Also for the spec: how the agents run. Two candidates to compare: the Claude API (separate account, pay per use,
   hard spending limit) or scheduled Claude Code sessions on the owner's subscription (no API account). To research
   first: what the subscription's terms and usage limits allow for scheduled, unattended runs, and whether every
   decision can be logged just as completely. The owner has no API account yet (2026-11-16).
   A third candidate (owner's idea): the owner opens a session by hand on most days and it does that day's round.
   Then decide beforehand what a skipped day means, so that skipping can never be a choice made with hindsight.
   Checked in the official documentation on 2026-11-16 (details and links: docs/research/notes/H-how-agents-run.md):
   cloud scheduled tasks exist for subscriptions but cannot read files on this machine; scheduling inside a session
   expires after seven days; a timer that starts Claude Code without a person is documented, but the terms do not
   say clearly that this is allowed on a subscription; with an API key it clearly is. Opening a session by hand is
   ordinary use. **Owner's direction (2026-11-16): sessions opened by hand, not scheduled ones**; the spec works
   this out (rule for skipped days, fixed moment at which decisions count) and records it as a decision.
   Owner's preference for models (2026-11-16): most agents Opus on high effort, the most important
   role on the strongest model; to weigh against a cheap model for the daily screening. Measure usage in the pilot.
2. Historical study: event studies (how small-biotech prices move around readouts, FDA dates, financing) and a case library of
   "missed" situations; this decides which data sources to build first.
3. Build those data streams on top of the archive (prices, SEC filings, the company linking table).
4. One-week pilot with one fund setup to measure real token cost.
5. Parallel setups live for ~6 months.

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
Published decisions are never edited afterwards, and the commit dates show that nothing was added with hindsight.
The record will be built from real market and trial data; the data files themselves are not published (see below),
only our own numbers and conclusions, with the sources named. The exact form is decided in the spec.

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
