# 0003. How the agents run: sessions opened by hand, skipped days, and the moment a decision counts
Date: 2026-11-17
Status: proposed

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

### 2. A fresh session, and one round a day
The script refuses to start a round unless all of these hold:
- the session was just opened, or just emptied with `/clear`. Claude Code tells a small helper (a "hook") how each
  session began. A session that was resumed, shortened or copied from an earlier one still carries old reading, and
  is refused;
- this session has not done a round before;
- no round was committed yet for this calendar day (Amsterdam time), except the single restart the spec allows after
  a crash before step 6;
- no `STOP` file is present in the data folder.

Refusals and restarts are written to the log.

### 3. What the agents can touch
The spec says the agents get no web search and no web access. This record makes that precise, because a
command line can fetch web pages too: **every agent file lists exactly the tools it may use, and the list holds only
tools that read files inside the folder prepared for this session.** No command line, no web tools, no connectors to
outside services. An agent file without such a list would get every tool, so a test checks every agent file for it.
Everything that computes, downloads, writes the log or publishes is done by scripts.

### 4. Skipped days and the fill day
As in the spec, section 2, unchanged:
- a day without a session is a day without trades for all five funds; nothing is caught up;
- the fill day follows from the start time written down in point 1: started before 14:00 Amsterdam time on a US
  trading day and published at least 30 minutes before the US market opens gives that day's opening price; every
  other case gives the opening price of the next US trading day;
- a decision is final when it is committed, and public when GitHub has received it (record 0004);
- if publishing fails, the same commit is sent again; the agents never run twice for one day;
- skipped days are counted and shown.

### 5. The trading calendar
- A **hand-made list** of the days the New York Stock Exchange is closed, for the whole period of the experiment,
  copied from the exchange's page, with link and date, in the repository. The opening time is 09:30 New York time.
- Amsterdam and New York times are converted with the time-zone data that comes with Python, not by hand.
- A test compares the list with `exchange_calendars`. That library is used for the test only, not in the daily run.
- **Safety net:** when a fill is booked, the script checks that the day really has an opening price for the index
  funds. If the list said "trading day" and there is no price, the fill moves to the next day that has one, and the
  log says so. This covers unplanned closures.

## Differs from the spec
Two small corrections; the rules themselves stay as they are.
1. **A second period with a different opening time.** The spec names the two weeks in March 2027 (14 to 27 March)
   in which the US market opens at 14:30 Amsterdam time. The same happens from 31 October to 6 November 2027. It only
   matters if the experiment runs on after its 26 weeks.
2. **What the rule means in those weeks.** Published "at least 30 minutes before the open" then means published by
   14:00. A session takes 20 to 45 minutes, so in those weeks only a session started before about 13:15 gets the
   same day's opening price; a later one gets the next day's. The rule already gives the right answer; the owner
   should just know it.

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
- The fresh-session check rests on features of Claude Code that can change with a new version. If the check cannot
  tell how the session began, it refuses; it never guesses.
- To check in the pilot, besides the spec's own list: that `/clear` is reported as a fresh start; that the effort
  level set in an agent file is really used.
- Found on the way, for record 0009: Claude Code removes its own session records after 30 days by default and writes
  them with a small delay, so the copy for our data folder is best made (or completed) at the start of the next
  session. The usage percentages are only given to the status-line script, which must write them to a file for the
  session to read.

## Revisit
Revisit: by 2027-03, or when Anthropic changes its consumer terms or the usage rules of Claude Code, when a new
Claude Code version changes how sessions or agent files work, or when the pilot shows that a fresh session cannot be
told apart reliably.

## Sources
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
