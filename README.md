# Bobby Hedgefund

A paper-money biotech fund run by a team of LLM agents, fed by open data (clinical trials, FDA, SEC filings, papers,
earnings calls), run forward on the home server for about 6 months and compared with XBI, IBB, IWDA and real biotech funds (ARKG, 13F filers).

## Status
2026-11-15: project named Bobby Hedgefund (repo and folder `bobby-hedgefund`, renamed from biotech-agents). Idea brainstormed with Claude (see docs/IDEA.md, incl. a prior-art check). Project folder created; no spec, no code yet.

2026-11-15: overnight research done (branch `research-overnight`, PR open, not merged): what to reuse, which data to collect, and a first look at past cases. Start with docs/research/SUMMARY.md; it ends with the open questions for the spec interview. No code, nothing installed.

2026-11-16: owner's answers to the four start questions recorded in docs/research/SUMMARY.md (SEC contact address, public-repository rule, free sign-ups, start the archive now). **Day-1 archive built** (branch `day1-archive`): a nightly job that only saves public files their publishers overwrite. See "Day-1 archive" below and docs/decisions/0001.

## Next step
1. Owner: create the free accounts (a price service first; see docs/research/DATA-SOURCES.md section 15, point 3).
2. Interview + spec (docs/SPEC.md), in plan mode. Agenda: the open questions in docs/research/SUMMARY.md.
3. Historical study: event studies (how small-biotech prices move around readouts, FDA dates, financing) and a case library of
   "missed" situations; this decides which data sources to build first.
4. Build those data streams on top of the archive (prices, SEC filings, the company linking table).
5. One-week pilot with one fund setup to measure real token cost.
6. Parallel setups live for ~6 months.

## Day-1 archive
A job that runs every night at 23:30 and saves a few public files exactly as published, because their publishers
overwrite them. It does no analysis. What, where and why: docs/decisions/0001-day-1-archive-storage-and-backup.md.

- **Saved:** trial records with a company involved (ClinicalTrials.gov), five European Medicines Agency files, the
  Nasdaq symbol lists, and the daily holdings of the XBI fund.
- **Where:** `~/bobby-hedgefund-data/archive/` (never in git). The nightly home backup copies it to Google Drive.
- **If something fails:** a phone message "Bobby archive". Then:

```
cd ~/projects/bobby-hedgefund
uv run bobby-archive status        # last run per source, stored size
uv run bobby-archive verify        # re-reads every file and checks it against its fingerprint; changes nothing
uv run bobby-archive run           # run the daily download by hand
uv run bobby-archive baseline      # one-time full copy of the trial records (done 2026-11-16; --resume if interrupted)
systemd/install.sh                 # install or update the timer
uv run ruff check && uv run ruff format --check && uv run pyright && uv run pytest
```
