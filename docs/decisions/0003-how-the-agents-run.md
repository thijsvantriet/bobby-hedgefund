# 0003. How the agents run: sessions opened by hand, skipped days, and the moment a decision counts
Date: 2026-11-17
Status: accepted (owner, 2026-11-17: read the main points and said "merge")

## Context
The agents are Claude models. Something has to start them every day, and the way they are started decides three
things that are costly to change once the funds run:
- whether the use of the owner's Claude subscription is allowed at all;
- whether the owner, or the program, could pick results with hindsight (by choosing when to run, or by running again);
- at which price a decision is booked.

The spec made these choices (`docs/SPEC.md`, sections 1 and 2; owner, 2026-11-16 and 2026-11-17). This record
writes them down with their reasons, checks them against the documentation as it is today, and fixes the few details
the spec left open: how a session is recognised as fresh, which tools the agents get, and where the trading
calendar comes from.

Requirements: paper money only; no look-ahead; no money spent on models (the subscription, no API); the owner's
only action is typing one command; a decision is public before the price it gets exists.

## Options considered

**What starts the agents** (from `docs/research/notes/H-how-agents-run.md`, checked again 2026-11-17)

| Option | Runs without the owner | Allowed on a subscription? | Verdict |
|---|---|---|---|
| A. Claude API key, started by a timer | Yes | Yes, but paid per use | Ruled out: the owner spends no money on models |
| B. Subscription login, started by a timer | Yes | **Unclear.** The consumer terms bar automated access "except … via an Anthropic API Key or where we otherwise explicitly permit it" | Not without Anthropic's explicit yes |
| C. Scheduled task in the cloud, or in the desktop app | Yes | Yes, documented | Cloud: starts from a copy of the repository, so it cannot read the data folder, and the data may not be in a public repository. Desktop app: runs only while the app is open, is in beta on Linux, and runs a missed task once afterwards, which breaks the "nothing is caught up" rule |
| **E. The owner opens a session and types one command** | No | Yes: ordinary use | **Chosen** |

The letters are those of the research note. Its option D (a schedule inside a session that stays open) is left out:
such schedules end after seven days.

**The price a decision gets**

| Option | For | Against |
|---|---|---|
| The closing price of the day of the decision | Simple | On a late session that price already exists: the decision could have seen it |
| **The next opening price after publication** | The first price nobody could have known. It is what the free price data offers (one opening and one closing price a day), and it is the default in the common back-testing programs, which call filling at an already known price "cheating" | A decision made in the morning is booked a few hours later; a decision made in the evening, a day later |
| A price during the day (for example one hour after publication) | Closest to the decision | Needs paid minute-by-minute data |

**Where the list of US trading days comes from**

| Option | For | Against |
|---|---|---|
| **A hand-made list for the months the experiment runs**, copied from the exchange's own page with the link and the date | No dependency; ten lines a year; anyone can check it | Must be extended by hand; an unplanned closure (a day of mourning, a storm) is not in it |
| The open-source library `exchange_calendars` (Apache 2.0, active) | Kept up by others, many years | Brings the large pandas package into the daily run; unplanned closures depend on volunteers updating it |
| No list: the first day that has a price is the fill day | Always right afterwards | The session cannot say beforehand which day it is deciding for |

## Decision

### 1. Sessions opened by hand (option E)
- One Claude Code session per day, in the project folder, started by the owner typing `/bobbyhedgefund-day`. No
  timer, no scheduled task, no API.
- The command is a file in this repository (`.claude/skills/bobbyhedgefund-day/`), set so that only typing it
  starts it: a model cannot start it by itself.
- **The first thing the command does is run a script, before any model has read anything.** That script does the
  checks of step 1 of the spec and writes down the start time and the data cut-off. If it refuses, nothing else
  happens.
- **The data cut-off is that start time.** The script then fills a folder for this session with copies of the files
  the agents may read, and takes only files that the saved-files lists show as saved before the cut-off.
- **Which code runs.** The session runs the code of the main branch as it is on GitHub. The script first tidies up
  what an earlier session may have left behind, in this order:
  1. files in `track-record/` that were written but never committed (a crash in the middle of step 6) are removed;
     they are copies, the day's records are prepared in the data folder and only placed in `track-record/` at the
     moment of the commit;
  2. commits that the publishing script made earlier and that GitHub has not received yet (publishing failed) are
     sent now. Only commits made by that script, touching only `track-record/`, are sent this way.

  Then it refuses when another branch is checked out, when files have been changed and not committed, or when the
  local main branch still differs from the published one (for example because there is no internet: a session that
  cannot publish does not run). Work in progress can therefore never write the real log (the same idea as the
  installed copy that the nightly archive runs, `docs/decisions/0001`).
- Step 1 checks the morning price download (record 0007) as well as the nightly jobs.

### 2. A fresh session, and one round a day
The script refuses to start a round unless all of these hold:
- the session was just opened, or just emptied with `/clear`. Claude Code tells a small helper (a "hook") how each
  session began. A session that was resumed, shortened or copied from an earlier one still carries old reading, and
  is refused;
- this session has not started a round before, finished or not;
- no round was committed yet for this calendar day (Amsterdam time);
- no `STOP` file is present in the data folder.

**The one restart after a crash** (spec, section 2, point 5) happens in a new fresh session, because the crashed
one counts as used. It keeps the **first** start time and data cut-off of that day, so the fill day cannot move and
no newer data comes in; it re-uses the reports already saved and reads the same session folder. A second crash makes
the day a skipped day.

Refusals, restarts, and the creation and removal of the `STOP` file are noted in the data folder at once, and
written to the log as records in the next round that is committed. Nothing is written to `track-record/` outside
a round.

### 3. What the agents can touch
The spec says the agents get no web search and no web access. This record makes that precise, in two layers:
- **Every agent file lists exactly the tools it may use: only tools that read files.** No command line (a command
  line can fetch web pages too), no web tools, no connectors to outside services. An agent file without such a list
  would get every tool, so a test checks every agent file for it.
- **A file-reading tool can read any file on the machine, so the tool list alone is not enough.** A small check
  that Claude Code runs before every use of a tool (a "hook") allows an agent to read only inside the folder
  prepared for this session, and refuses everything else: the settings file with the keys, the rest of the data
  folder, other funds' private files, the repository's history, and any file that a download job writes while the
  session runs. A refused read is logged.

A test tries to read a file outside the session folder and a file saved after the cut-off, and must be refused both
times; the pilot repeats that test in a real session. Everything that computes, downloads, writes the log or
publishes is done by scripts.

### 4. Skipped days and the fill day
As in the spec, section 2, unchanged:
- a day without a session is a day without trades for all five funds; nothing is caught up;
- **the fill day, in one sentence used by every record: the first US trading day whose opening is at least 30 minutes after GitHub received the publication;
  and for a session started at or after 14:00 Amsterdam time, never the day of the session itself.** In the normal
  case this is exactly the spec's rule: started before 14:00 on a US trading day and published at least 30 minutes
  before the opening gives that day's opening price, anything else the next trading day's;
- a decision is final when it is committed, and public when GitHub has received it (record 0004);
- if publishing fails, the same commit is sent again; the agents never run twice for one day;
- skipped days are counted and shown;
- a weekend session is allowed only to make up for a working day skipped in that same week, counts as that working
  day, and is filled at the next trading day's opening price; US market holidays are not skipped days.

Because the fill day depends on when GitHub receives the publication, **a decision record states the rule, not the
day**. The day itself is stated in the fill record, written by the next session (records 0004 and 0005).

### 5. The trading calendar
- A **hand-made list** of the days the New York Stock Exchange is closed, for the whole period of the experiment,
  copied from the exchange's page, with link and date, in the repository. The opening time is 09:30 New York time.
- Amsterdam and New York times are converted with the time-zone data that comes with Python, not by hand.
- A test compares the list with `exchange_calendars`. That library is used for the test only, not in the daily run.
- **Safety net:** when a fill is booked, the script checks that the day really has an opening price for the index
  funds. If the list said "trading day" and there is no price, the fill moves to the next day that has one, and the
  log says so. This covers unplanned closures.

## Differs from the spec
Nothing in the rules changes. Three additions make them more exact.
1. **A second period with a different opening time.** The spec mentions the weeks in March 2027 in which the US
   market opens at 14:30 Amsterdam time; these are 14 to 27 March. The same happens from 31 October to 6 November
   2027. That only matters if the experiment runs on after its 26 weeks.
2. **What the rule means in those weeks.** Published "at least 30 minutes before the open" then means published by
   14:00. A session takes 20 to 45 minutes, so in those weeks only a session started before about 13:15 gets the
   same day's opening price; a later one gets the next day's. The rule already gives the right answer; the owner
   should just know it.
3. **Reading is limited by a check before every tool use**, not only by the agent files (point 3 above). The spec
   speaks of the agent files only.
4. **A gap closed in the fill rule.** The spec says "every other case: the next US trading day". If publishing
   fails and GitHub receives the commit only after that next opening, the spec's words would give a price that
   already existed. The sentence in point 4 ties the fill day to the moment GitHub received the publication, so
   that can never happen.
5. Refusals and stop-file changes reach the log in the next committed round, not at the moment they happen.

## Consequences
- The use of the subscription is ordinary use by its owner: one person, one session, started by hand.
- Nothing runs when the owner does not start it. Skipped days cost nothing but are visible; fewer than half of the
  working days for two months stops the experiment (spec, section 9).
- Hindsight is closed off in three places: the start time is recorded before anything is read, a session cannot do
  a second round, and the price is one that did not exist yet.
- The agents depend completely on what the nightly jobs saved. Something that was not downloaded cannot be looked
  up during a session.
- Agents without a command line cannot run a calculation themselves; every number must be prepared by a script.
  That is rule 7 of the research anyway.
- The fresh-session check and the reading check rest on features of Claude Code that can change with a new
  version. If a check cannot tell how the session began or where a file is, it refuses; it never guesses.
- The owner must have the main branch checked out and clean when starting the day's session; otherwise the command
  refuses and says why.
- To check in the pilot, besides the spec's own list: that `/clear` is reported as a fresh start; that the effort
  level set in an agent file is really used.
- **Owner, 2026-11-17: after the pilot week, review how much the agents miss by having no web access** (for
  example a news article they would have wanted to look up). The session notes every time an agent says it lacked
  something. If it is a real problem, the way out that keeps the data cut-off is to save more beforehand (the
  company news feeds of stream 6, earlier than planned), not to let agents browse during a session.
- Found on the way, for record 0009: Claude Code removes its own session records after 30 days by default and writes
  them with a small delay, so the copy for our data folder is best made (or completed) at the start of the next
  session. The usage percentages are only given to the status-line script, which must write them to a file for the
  session to read.

## Revisit
Revisit: by 2027-03, or when Anthropic changes its consumer terms or the usage rules of Claude Code, when a new
Claude Code version changes how sessions or agent files work, or when the pilot shows that a fresh session cannot be
told apart reliably.

## Update 2026-11-18: how the session folder is built
Command: `bobby-session prepare` (README, "Session preparation").
- **The cut-off in practice.** A saved file is taken when the time in its line of the saved-files list lies
  before the cut-off; every file is re-checked against its fingerprint when it is read. A file our own jobs made
  has no such line: it is taken only when its own list of inputs says it was made before the cut-off and every
  file in that list was saved before it. The newest usable file is chosen by the date in its name, never by a
  date of the file system.
- **The list of inputs** (`inputs.jsonl`) numbers every source: the universe file, each new filing, each trial
  record behind a change, the price file the numbers come from. The session's first log record carries the
  fingerprint of this list (record 0004), so it can be shown later what a session could read.
- **What an agent can read about a company:** who it is, what is new, the new filings as plain text, the changes
  in its trial records, numbers from saved prices marked private, and our own last report. Nothing else: the
  saved-files lists, the price files and the universe file themselves are not in the folder.
- **What counts as new** is what no earlier session was shown: every earlier session's list of inputs is read,
  and a filing or a change in a trial record that is in one of them is not shown again. So an item that a job
  found late (a download or a comparison that ran after the session it belonged to) is still shown once. It must
  be saved before the cut-off and be no older than three days before the last session; older ones are counted
  and left out.
- **A change in a trial record is not taken on trust.** The page it names must be in the saved-files list, saved
  at the time the line says, before the cut-off; otherwise the line is left out and counted.
- **Filings a company makes as a holder.** A company's list of filings also holds what it files as an owner of
  another company's shares. Such a filing is marked "filed as a holder of another company", shows its parties,
  and does not by itself send the company to the screening.
- **Left out in one place:** companies in the universe through the XBI fund only (record 0009, open point 2).
  Their names are also taken out of every text that is copied into the folder (a filing of another company can
  name them) and replaced by "[a company that is not named]". The private list of those names only grows: a
  company once on it stays, and names added by hand are kept. A universe file that marks no such company at all
  gets a warning.
- **The folder is built under another name** and gets its own name in one step when it is complete, so a
  preparation that stops half-way leaves nothing that could be taken for a session folder.
- **Our own earlier report** on a company is copied in only when it is of an earlier session day; a link is not
  followed.
- **A move of the share "since the last session"** is measured against the newest price day that session could
  see, not against the calendar: the final copy of a day's prices arrives a day or two later.
- **Found on the way.** (1) The first big download of filings was saved in one go, so everything in it looked
  new; a filing counts as news only when it was also filed around the last session (three days of margin). (2)
  The price service marks the newest day "delayed" until the next morning's download, and the books use final
  copies only: on a morning session the numbers are from two trading days before, and a fill is booked one
  session later than the calendar alone would allow. No rule is broken by that; the pilot shows whether it
  matters. (3) The first run on real data: 215 companies, 637 new filings, 37 MB, about a minute (a quarterly
  report is several megabytes; turning them into plain text with a parser took most of the time, so that is
  done with patterns now). A normal day will have a few dozen filings. (4) Known and not solved here: a filing
  that two companies file together is saved once, under the first, so the second does not get it (stream 2).

**Review.** A reviewer agent (Opus) read the code and found no way for anything saved after the cut-off to get
into the folder, but said "fix first" for other things, all worked in above: the rule for a move of the share
compared against the wrong day, so it would never have fired in a morning session; trial changes found late
were dropped for good; filings made as a holder were shown as the company's own; the private list was rebuilt
from scratch each day; a half-built folder blocked the day for good; reports were copied without a check on
their day; a time without a zone crashed; a trial-change line was trusted as it stood; the list of tasks could
be changed unnoticed.

Read on 2026-11-17 unless noted.
- Claude Code documentation: [skills and typed commands](https://code.claude.com/docs/en/skills.md),
  [agent files](https://code.claude.com/docs/en/sub-agents.md), [hooks](https://code.claude.com/docs/en/hooks.md),
  [where sessions are stored](https://code.claude.com/docs/en/claude-directory.md),
  [status line](https://code.claude.com/docs/en/statusline.md),
  [scheduled tasks in the desktop app](https://code.claude.com/docs/en/desktop-scheduled-tasks.md),
  [running without a person](https://code.claude.com/docs/en/headless.md)
- Terms: [Anthropic consumer terms](https://www.anthropic.com/legal/consumer-terms),
  [Claude Code legal and compliance](https://code.claude.com/docs/en/legal-and-compliance.md)
- Filling at the next opening price: [Backtrader, "cheat-on-open"](https://www.backtrader.com/docu/cerebro/cheat-on-open/cheat-on-open/),
  [QuantConnect, market orders outside trading hours](https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/order-types/market-orders)
- Fixing a prediction before the outcome exists: [OSF registrations](https://help.osf.io/article/330-welcome-to-registrations),
  [Center for Open Science on preregistration](https://www.cos.io/initiatives/prereg),
  [ForecastBench](https://arxiv.org/abs/2409.19839) (only questions without a known answer at the time of the forecast)
- Trading days and hours: [NYSE hours and calendars](https://www.nyse.com/markets/hours-calendars).
  Clock changes: [EU directive 2000/84/EC](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32000L0084); US and
  EU dates for 2027 checked against Python's time-zone data
- [exchange_calendars](https://pypi.org/project/exchange-calendars/) (Apache 2.0)
- Earlier research: `docs/research/notes/H-how-agents-run.md`; `docs/research/OPEN-SOURCE.md`, 3.5

Not verified: the Nasdaq holiday page did not load (the New York Stock Exchange list is used; the two exchanges are
believed to close on the same days). Whether `/clear` gives a session a new identity is checked in the pilot.
