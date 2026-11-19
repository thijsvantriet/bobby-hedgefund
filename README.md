# Bobby Hedgefund

A paper-money biotech fund run by a team of LLM agents, fed by open data (clinical trials, FDA, SEC filings, papers,
company news), run forward for 26 weeks and compared with two funds without AI and with index funds (XBI, IBB and
a world index fund; docs/SPEC.md).

**This is an experiment with paper money. Nothing here is investment advice, and no real money is traded.**

**How far it is (2026-11):** the research reports, the nightly data archive and the data streams the pilot needs exist. There are no agents, no
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

2026-11-18: parts 1 and 2 merged into `main` (PRs #12 and #13) and installed for the nightly job. The one-time fetch of the SEC company files was started the same morning as a background service of its own (about 1,000 of 6,051 companies done at the merge). Check it with `bobby-archive status` (the line `sec`) or `systemctl --user status bobby-sec-companies`; if it stopped early, `bobby-archive sec-companies --resume` continues it.

2026-11-18: **the owner wants the pilot at the end of November 2026**, not in January. The order of work stays; see "Next step" for what must exist by then.

2026-11-18: **stream 1: daily prices built** (`bobby-prices`, see "Daily prices" below; docs/decisions/0007, "Update 2026-11-18"). One request gives the whole US market for one day, with prices as they were traded; the file is stored as received, in a folder of its own with its own list of fingerprints, apart from the archive (the price service's terms require that everything can be deleted if the account ends). Also stored: the service's list of share splits. A morning timer fetches the last day, and each new day is compared with the day before. The one-time download of the two years the free plan offers was started the same day. Nothing from this folder is ever published.

2026-11-18: **the price history is complete**: 501 trading days, 18 November 2024 to 17 November 2026, every file checked against its fingerprint. Found on the way: the service marks the newest day "delayed" for some hours; such a copy is stored with that mark and the final one is fetched later (docs/decisions/0007, "Update 2026-11-18").

2026-11-18: **stream 0 finished up to the owner's check** (docs/decisions/0006, "Update 2026-11-18", with the counts of the first run). The SEC company files are complete (6,051 companies). Built and run: the candidate list (704 companies), the reported share counts from the SEC (`bobby-archive sec-shares`), the filter (`bobby-universe build`: **221 companies in the first universe**, the spec expected 150-250), the name matching with its review sheet (`bobby-universe match`: 311 suggested sponsor names for the owner to judge; nothing is accepted automatically), and the commands that take the owner's decisions over and build the linking table from them. **Waiting for the owner: the one-time check of the review sheet.** Six companies of the universe come in through the XBI fund only and are therefore not named publicly.

2026-11-18: **stream 2: SEC filings built** (docs/decisions/0008, "Update 2026-11-18 (2)"). The nightly archive run now also fetches, for every company of the universe, its filing list and each new filing of the followed kinds since 1 September 2026, as received. A weekly cross-check against the SEC's own daily list of filings, and a reading step for the items of an event report and the lines of an insider trade. Our own small reader is used; edgartools was not tried and stays the candidate for the quarterly reports of stream 4.

2026-11-18: **stream 3: trial-record changes built** (`bobby-trials changes`, see "Trial-record changes" below). A nightly job reads every archived copy of every trial record and lists each change in a fixed set of fields (status, dates, phases, number of patients, primary outcomes, sponsor, results), with the two archived files the old and the new value come from. First run: 798 changes in 302 trials since the first copy of the registry of 2026-11-16; three were compared with the raw records by hand. With this, streams 0-3 are built.

2026-11-18: **rules for the historical study drafted** (docs/study/RULES.md, status "proposed"): what it must deliver (base rates and the typical size of a price move), which past results are in it and how the list is made before any outcome is looked at, the measures, the time limit of six sessions. Nothing is downloaded or analysed until the owner says yes; four questions for the owner are at the end of that document.

2026-11-18: streams 0-3 merged into `main` (PRs #15, #16, #17) and installed: prices every morning (07:30, again 12:30), SEC filings inside the nightly archive run, trial-record changes at 01:15. 272 tests pass; three reviewer runs (Opus) before the merge, their findings worked in. Checked after the install: archive and prices pass their fingerprint check.

2026-11-18: **record 0009 drafted** (docs/decisions/0009, "proposed" until the owner merges it): the agent team as files with a fixed model, effort and tool list; model and effort are read by script from each agent run's own record and compared with the file; an agent's answer is taken from that record too, so the session that starts the agents cannot change it; every portfolio-manager round runs three times. Checked against the Claude Code documentation; seven points that documentation could not settle are listed as pilot checks. Three open points for the owner, each with a default.

2026-11-18: **the decision log built** (`bobby-log`, `bobby-publish`; docs/decisions/0004, "Update 2026-11-18"; see "Decision log" below). Lines that are only ever added, each with the fingerprint of the line before it, also across day files; content that may not be public (everything from prices) goes to a private file and the public line shows only its fingerprint; written text is checked for long quotes, prices and untraceable amounts before a line is written; the publish script only adds to `track-record/` and refuses everything else. Tried in a scratch folder: a changed, removed, re-ordered and lost line and changed private content are each caught. Only the pilot mode is switched on: nothing is sent to GitHub, and the real log stays off until the owner's go.

2026-11-18: **the fund books built** (`bobby-funds`; docs/decisions/0005, "Update 2026-11-18"; see "Fund books" below). The books are recomputed from the decision log: a fill is a logged fact and is never worked out again. Booking walks through every trading day since the last one booked and follows the rules of record 0005 to the cent (whole shares, sells before buys, buys cut in proportion, the 0.5% minimum, the five-day wait, the 30% brake). The risk limits are checked in code when a decision is made, and a refused or reduced order is logged. Share splits and takeovers for cash and for shares are booked; the rarer events are refused until built. The Dice fund is complete (a draw anyone can repeat from fingerprints, 1,000 funds in private files); the Rules fund has its selection rule but holds nothing until streams 4 and 5 give it its inputs. Tried on the real saved prices with made-up orders: 75 trading days, 23 fills, one real share split, 1,000 Dice funds, and a full recomputation equal to the cent. No broker, no real order: paper money only.

2026-11-18: **the session preparation built** (`bobby-session prepare`; docs/decisions/0003, "Update 2026-11-18"; see "Session preparation" below). At a data cut-off it builds the folder the agents may read: per company what is new since the last session (SEC filings as plain text, changes in trial records, numbers worked out from saved prices), a screening list in batches, and a numbered list of every source with its fingerprint and the time it was saved. Only files saved before the cut-off are used; a file our own jobs made is admitted only when all of its inputs were saved before it. The companies that may not be named in public get no folder at all. Trial changes are linked to a company once the linking table exists; until the owner's check they are counted and left out. Tried on today's real data: 215 companies, 637 new filings, about a minute.

## Next step
The plan is docs/SPEC.md ("Order of work"). In short:
1. ~~Owner reads and merges the spec~~ (done 2026-11-17). ~~Decision records 0003-0008~~ (accepted 2026-11-17).
   Records 0009-0014 follow when their step comes (spec, section 10).
2. **Now:** build data streams 0-3 on top of the archive: the linking table (with the owner's one-time check of about 200
   matches), daily prices, SEC filings, trial-record changes. The terms for prices and SEC filings are read
   (0007, 0008). Stream 0, parts 1 and 2 (the SEC company files, the candidate list and the sponsor
   names), stream 1 (daily prices), the filter, the name matching and stream 2 (SEC filings) are built.
   Stream 3 (trial-record changes) is built too; all four streams run (merged 2026-11-18).
   **Waiting for the owner:** fill in the review sheet of suggested matches (`linking/<date>_review.xlsx`, the
   newest one; 221 companies), then `bobby-universe decisions <sheet>` and `bobby-universe linking`
   make the linking table. After that: the by-hand check of 20 companies for missed names.
   Alongside: the historical study, limited to two weeks of work. Its rules are drafted (docs/study/RULES.md)
   and wait for the owner's yes; its AACT download is settled (0014).
3. **Now (Claude):** record 0009, agent files, decision log and fund books; then the one-week pilot with one fund, which measures how much of the
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

## Daily prices (stream 1)
Design: docs/decisions/0007. Stored in `~/bobby-hedgefund-data/prices/` (never in git, **never published**: the
price service's terms forbid it), with its own list of fingerprints. A timer runs `bobby-prices daily` at 07:30 and
12:30; a failure sends a phone message "Bobby prices".

```
bobby-prices status                # last run, and which days are stored
bobby-prices verify                # re-reads every file and checks it against its fingerprint; writes nothing
bobby-prices daily                 # the morning download by hand: missing days of the last two weeks, the splits
bobby-prices backfill              # one-time: two years of history (about 2 hours; run it again to continue)
bobby-prices check --days 5        # list closing prices that moved by more than half without a share split
bobby-prices purge                 # deletes every saved price; only for the day the account with the service ends
```

- One file per trading day: opening, highest, lowest and closing price and the volume of every US share, as they
  were traded on that day (not recalculated afterwards for share splits). Plus the service's list of share splits.
- There is no second price source. Instead `check` compares each day with the day before and writes
  `prices/checks/<date>_jumps.csv`: a list to look at, not a list of errors (a trial result can halve a share).
- A working day without prices counts as "market closed" only when it is more than four days old and is a regular
  US market holiday, or when the service said so twice. A recent day that looks half-filled is asked again.

## Universe and linking table (stream 0)
Design: docs/decisions/0006. The commands read the archive and the prices and write dated files next to them; they
never replace a file (a second run on one day gets `-2` in its name). The results are private: they hold the XBI
flag and numbers computed from prices, and are never committed.

```
bobby-universe candidates          # companies that can enter the universe, before the filter on size and trading
bobby-archive sec-shares           # monthly, by hand, after sec-companies: the candidates' reported share counts
                                   # (about 45 minutes; run it again to continue; --limit N for a first try)
bobby-universe build               # the universe: every candidate through the filter, with the numbers used
bobby-universe sponsor-names       # every company-like sponsor name in the archived trial records (2 minutes)
bobby-universe match               # suggested sponsor names per universe company: the review sheet for the owner
bobby-universe decisions <sheet>   # take over the owner's decisions from the filled-in review sheet
bobby-universe linking             # the linking table (company, sponsor names, trials) from the decisions so far
bobby-universe missed-check        # draw 20 companies at random for a by-hand search for missed names
```

- `universe/<date>_candidates.csv`: one line per company with one of our four industry codes or a place in the
  XBI fund: SEC company number, name, tickers, industry code, the door it came through, whether it reports as a
  foreign company (left out of version 1), former names, a check of its ticker against the Nasdaq lists, and the
  name the fund's file gives it. A fund holding that cannot be linked to exactly one company goes to
  `<date>_xbi-unmatched.csv` instead of being guessed. `<date>_inputs.txt` lists the archived files that were
  read, with their fingerprints.
- `universe/<date>_universe.csv`: every candidate with "in" or "out", **every** rule it fails, and the numbers
  used with their dates: the share count and where it comes from, the last closing price, the market value, the
  average traded per day over 60 trading days. The rules are those of record 0006: market value $300 million to
  $10 billion, at least $2 million traded a day, share price at least $2, listed on Nasdaq or the New York Stock
  Exchange, not a shell company, not a foreign filer, not marked "not biotech" by the owner. It refuses to run on
  incomplete share counts or on prices older than a week.
- `linking/<date>_review.xlsx`: the sheet the owner fills in. One grey line per company, under it the sponsor
  names from the trial registry that may be the same company, with a column "decision" (yes / no / parent or
  subsidiary; on the company line: not biotech). **Nothing is accepted automatically.** A read-only machine copy
  (`<date>_review.csv`) is kept next to it, and a filled-in line is only taken over when it still agrees with that
  copy, so a slip of the keyboard in another column cannot link a wrong name.
- `linking/decisions.jsonl`: the owner's decisions, one per line; the file only ever grows. A changed mind is a
  new line that points to the old one; every line carries the fingerprint of the line before it.
- `linking/<date>_linking.csv`: the linking table as it follows from the decisions on that date: company, sponsor
  name, relation, its trial numbers. Trials run by a partner under another sponsor name are missing until the
  drug-name step is built.
- `linking/<date>_sponsor-names.csv`: sponsor name as written in the registry, its classes, number of trials,
  one example trial.
- In these files a text that a spreadsheet would run as a formula (starting with `=`, `+`, `-` or `@`) has an
  apostrophe in front.

## SEC filings (stream 2)
Design: docs/decisions/0008. The nightly archive run fetches, for every company in the newest universe file, its
filing list and each new filing of the kinds we follow, as the one complete text file, stored as received in the
archive (`raw/sec-filings/`). Followed: event reports (8-K), share sales (S-3, 424B5), insider trades (Form 4),
holders of more than 5% (Schedule 13D and 13G), quarterly and yearly reports (10-Q, 10-K), and their amendments;
from 1 September 2026 on. One request a second; a refusal stops the job for that night.

```
bobby-archive sec-filings          # the same job by hand, for the first fetch (--limit N for a first try)
bobby-archive sec-crosscheck       # weekly, by hand: compare with the SEC's own list of each day's filings
bobby-filings recent --days 7      # what was stored: the items of each event report, the lines of insider trades
```

Reading (`src/bobby_hedgefund/filings/`) never touches the network: it takes the kind of filing, its dates, the
items of an event report and the transactions of an insider trade from the stored file. The filings' own text
belongs to the companies: it is only summarised and linked, never republished at length.

## Trial-record changes (stream 3)
A timer runs `bobby-trials changes` every night at 01:15, after the archive run. It downloads nothing: it reads
every archived copy of every trial record, oldest first, and lists each change in a fixed set of fields, with the
old and the new value and the two archived files they were read from.

```
bobby-trials changes               # by hand; a few minutes; writes only changes no earlier run wrote
```

- Followed fields: overall status, why stopped, start date, primary completion date, completion date, phases,
  number of patients, primary outcomes (measure and time frame), lead sponsor, has results, results first posted.
  For a date the line also says how many days it moved. The list is fixed in
  `src/bobby_hedgefund/trials/changes.py`: the spec's one side-hypothesis (registry edits against later price
  moves, docs/SPEC.md section 4) is measured on it, so changing it later is a change of that measure.
- `~/bobby-hedgefund-data/trial-changes/<date>_changes.jsonl`: one line per change. Each run writes only what
  is new; all the dated files together are the full list since the first copy of the registry (2026-11-16). A
  night without news writes nothing. `<date>_changes-inputs.txt` lists the archived files that were read.
- Shown this way is what the registry *posted*; a change is seen on the night its record was archived.
- An archived page or record that cannot be read is counted and reported once (phone message "Bobby trials"),
  not every night.

## Session preparation
Design: docs/decisions/0003 (point 1) and 0009. The first thing a daily round does, before any model has read
anything.

```
bobby-session prepare              # build today's session folder at the data cut-off (now)
```

- **Where:** `~/bobby-hedgefund-data/pilot/sessions/<date>/` (never in git; it holds numbers from prices and text
  from filings). Made once per day and never changed; its files are read-only.
- **Only what was saved before the data cut-off.** A saved file counts by the time in its line of the saved-files
  list, never by a date of the file system. A file our own jobs made (the universe, the linking table) is used
  only when every file in its own list of inputs was saved before the cut-off.
- **Per company** (`companies/<SEC number>/`): `company.md` (who it is, what is new since the last session),
  `numbers.md` (worked out by script from saved prices; private), `trials.md`, the new filings as plain text
  (the form itself and its press releases), and our own newest report on it.
- **`inputs.jsonl`**: one numbered line per source with its fingerprint, the time it was saved and its link. The
  agents name their sources by these numbers; the session's first log record carries the fingerprint of this list.
- **Screening:** `screening/batch-NN.md` with a short digest per company that has news, 25 a file. Companies
  without any new item are listed in `no-news.txt` by the script and are sent to no model.
- **What counts as new:** what no earlier session was shown (their lists of inputs are read), saved before the
  cut-off. A filing or a change older than three days before the last session that was only fetched now is left
  out (and counted). A move of the share of 15% or more since the prices the last session saw counts as an item
  by itself. A filing a company made as a holder of another company's shares is marked as such and is no news
  about the company itself.
- **Not in the folder at all:** the companies that are in the universe through the XBI fund only (record 0009,
  open point 2). Their names go to a private list that only grows; they are taken out of every text copied into
  the folder, and the log and the publish script use the list as a last check.
- **Trials** are linked through the linking table once the owner's check has made one; until then each company's
  trial file says "not linked yet" and the changes are only counted.
- **Who gets a deep analysis** (`session/select.py`, the order of the spec): holdings with news, then what the
  screening flagged, then a catalyst within 60 days, then the rest in a fixed rotation.

## Decision log
Design: docs/decisions/0004 and 0009. Until the funds start only the **pilot** log exists, in
`~/bobby-hedgefund-data/pilot/` (never in git, never sent anywhere); the real one starts with the owner's go.

```
bobby-log verify                   # re-check the whole chain of fingerprints and the private files; writes nothing
bobby-log verify --dir <folder>    # the same for a copy of track-record/ (anyone can run this; public half only)
bobby-log show --day 2026-11-30    # print records (--open also shows sealed content: private)
bobby-log head                     # the newest fingerprint and the number of records
bobby-publish plan                 # what publishing would do; writes nothing
bobby-publish day 2026-11-30       # the day's one commit (pilot: in a repository inside the pilot folder)
```

- `staging/`: the public files as they are prepared, exactly the tree that is placed in `track-record/`:
  `log/<year>/<month>/<date>.jsonl` (one record per line), `HEAD` (newest fingerprint and number of records),
  `forecasts.csv` (only grows; an outcome is a new line).
- `log-private/`: per record with sealed content one file with that content and the random values. Falls under
  the deletion rule for prices (`bobby-prices purge`); after it `verify` reports "content deleted under record
  0007" instead of damage.
- **The fingerprint of a record** is the SHA-256 of: the fingerprint of the record before it, a line-feed, and the
  bytes of the line. The first record starts from a fixed value: the SHA-256 of the text
  `bobby-hedgefund decision log, format 1, live` (for the pilot the last word is `pilot`, so a pilot record can
  never be placed in the real log).
- **A sealed field** shows the SHA-256 of: a random value (64 characters), a line-feed, and the content written in
  the log's fixed form. Example to check a program against: random value sixty-four zeros and the content
  `"12.34"` give this fingerprint (sha256): `2c8629da9624bda7b55097b55a1f701433a8d067599434728e2f7fd1b28d4f21`.
- The fixed form of a line: field names in alphabetical order, no spaces, letters outside the basic English set as
  codes, and no number with a decimal point (money is whole cents, a percentage is text such as `2.5%`).
- Live mode refuses to run until a file named `LIVE` exists in the data folder: the owner's go.

## Fund books
Design: docs/decisions/0005. **Paper money only: there is no broker and no real order; a trade is a line in our own
log.** Everything these commands compute comes from prices and stays in the data folder.

```
bobby-funds start --funds careful,rules,dice   # start funds with $1,000,000 of paper money each
bobby-funds book                   # book fills, share splits, takeovers and the values since the last booked day
bobby-funds draw                   # first session of a month: the Rules and Dice funds are drawn anew
bobby-funds check                  # recompute every stored value from the log and the saved prices
bobby-funds status                 # positions, cash and waiting orders (private: for your own screen only)
bobby-funds event --kind "cash takeover" --cik ... --effective ... --filing <SEC link> --cash-per-share 12.50
```

- **The log is the only truth.** Positions, cash and values are added up from its records; `check` does that
  again from scratch and compares with what was stored, to the cent.
- **Booking** goes trading day by trading day, also over days without a session. It stops at a trading day whose
  price file is not stored yet, at a day newer than the saved list of share splits, and before the day of a
  session whose time of publication the log does not hold yet (its orders have no fill day until then).
- **The fill day** follows from when the day's publication was received (docs/decisions/0003): the first trading
  day whose opening is at least 30 minutes later, and never the session's own day when it started at or after
  14:00 Amsterdam time. The days the exchange is closed are a hand-made list in `funds/calendar.py`, copied from
  the exchange's page; it covers 2026 and 2027 and must be extended for later years.
- **Limits in code**, checked when a decision is made, with waiting orders counted as filled: at most 5% per stock
  (8% for Bold), 25 positions, 3 positions with a make-or-break result within 30 days (8 for Bold), only covered
  companies of the universe, nothing bought at 30% or more below the fund's own highest value, no trade below
  0.5%, one order per company in a round. The public log does not name that 30% rule when it stops a buy, and
  seals a size that follows from what a position is worth: both would give a return away.
- **Company events.** Share splits come from the saved list of splits and are marked "not checked against the
  filing". A takeover is entered by hand from its SEC filing with `bobby-funds event` and booked in the next round.
- **Dice.** For fund number n, every covered company gets the SHA-256 of the text made of the starting number,
  the month (`2027-02`), n and the company's SEC number, each on its own line; the fund holds the 20 with the
  lowest fingerprints. The public log holds the starting number and each month's covered list; the funds' orders,
  fills and values are in private files whose fingerprints are logged (sealed).
- **Rules** holds nothing until a file with the months of cash and the catalysts exists (streams 4 and 5); its
  exact rules, like those of Dice, are fixed in record 0010.
- The index funds XBI, IBB and URTH are bought on day one and held; their values are stored privately only.

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
| [U.S. Securities and Exchange Commission, EDGAR](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) | The ticker file and each listed company's filing list; reported share counts of candidate companies; filings of the universe's companies; the daily index of filings (from 2026-11-18) | Free for everyone; at most one request a second with a declared contact, as the SEC asks; the filings' own text belongs to the companies and is only summarised and linked, never republished at length (docs/decisions/0008) |
| [Massive](https://massive.com/) (closed, commercial service; free plan) | Daily prices of all US shares, and the list of share splits (from 2026-11-18) | Personal use only. **Nothing from it is published, and nothing computed from it**: no price, no fund value, no return ([terms](https://massive.com/legal/market-data-terms-of-service); docs/decisions/0007). Everything saved is deleted within 30 days if the account ends. At most five requests a minute |

Sources that were only read for the research are linked where they are used in `docs/research/`. Candidates for later
streams, with their terms: docs/research/DATA-SOURCES.md.

## Licence
Code: MIT (`LICENSE`). Reports, decision records and results (`docs/`, this README): Creative Commons Attribution 4.0
(`LICENSE-CC-BY-4.0`). Why: docs/decisions/0002-licences-mit-and-cc-by.md. Files from the data sources are not part
of this repository and keep their own terms.
