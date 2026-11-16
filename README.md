# Bobby Hedgefund

A paper-money biotech fund run by a team of LLM agents, fed by open data (clinical trials, FDA, SEC filings, papers,
earnings calls), run forward on the home server for about 6 months and compared with XBI, IBB, IWDA and real biotech funds (ARKG, 13F filers).

## Status
2026-11-15: project named Bobby Hedgefund (repo and folder `bobby-hedgefund`, renamed from biotech-agents). Idea brainstormed with Claude (see docs/IDEA.md, incl. a prior-art check). Project folder created; no spec, no code yet.

2026-11-15: overnight research done (branch `research-overnight`, PR open, not merged): what to reuse, which data to collect, and a first look at past cases. Start with docs/research/SUMMARY.md; it ends with the open questions for the spec interview. No code, nothing installed.

2026-11-16: owner's answers to the four start questions recorded in docs/research/SUMMARY.md (SEC contact address, public-repository rule, free sign-ups, start the archive now). **Day-1 archive built** (branch `day1-archive`): a nightly job that only saves public files their publishers overwrite. See "Day-1 archive" below and docs/decisions/0001. First runs done the same day: the one-time full copy of 170,083 company-linked trial records (444 MB) is stored and the whole archive passes its check. Known issue: the EMA site refuses one of its five files now and then, so an occasional "Bobby archive" phone message about EMA is expected.

2026-11-16: owner created the free accounts; keys are in the local `.env` (never in git). Eight of nine tested and working (Tiingo, Massive, openFDA, FRED, NCBI, FDA Data Dashboard, OpenAlex, AACT); EPO waits for approval. AACT's key turned out to give dated full copies of the registry, monthly back to 2017: the base for the historical study (details in docs/ACCOUNTS.md).

## Next step
1. Owner, when EPO approves the account: put its Consumer Key and Secret in `.env` (only needed if patents make it into the spec).
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
