# Bobby Hedgefund: specification, version 1

Date: 2026-11-17. Status: **approved** by the owner on 2026-11-17 (merged as PR #8).
Drafted by Claude from the research in `docs/research/`. The owner acts as process facilitator and decided the eight
points marked **Owner** (asked on 2026-11-17). Everything else is a recommendation with a one-line reason, and can be
changed at a monthly review (section 9).

**Paper money only. Nothing here is investment advice, and no real money is traded.**

## 0. In short

- A team of AI agents runs three paper funds of small and mid-size biotech companies, next to two funds without AI
  and three index funds, for 26 weeks.
- The agents work in one Claude Code session a day that the owner opens by hand. No scheduled sessions, no Claude API.
- Every decision is written to a public log with its reasoning *before* the market can act on it, and is never
  edited afterwards.
- The experiment does not try to prove that the agents beat the market: six months is too short for that
  (`docs/research/OPEN-SOURCE.md`, 3.4). It measures two things that six months *can* show: **differences between
  fund setups**, and **whether the agents' stated probabilities are any good**.

Fixed earlier, not reopened here: paper money only; agents are tested forward only; every decision logged and never
edited; sessions opened by hand; the repository is public, holds no keys, addresses, home details or source data, and
follows and credits every source (`CLAUDE.md`, README "Data sources and credit").

## 1. The daily session

The owner opens a Claude Code session in the project folder and types `/bobbyhedgefund-day`. **That is the owner's only
action** (owner, 2026-11-17: one thing per session, not three). Everything after it runs by itself, including
publishing; the owner may walk away.

**Every day's round starts in a fresh session**: a new session, or `/clear` in the one still open from the day
before. The session does not close itself when the round is done; it waits, which uses nothing. The command refuses
to run in a session that has already done a round, so yesterday's reading can never leak into today's.

| # | Step | Done by | Ends by minute |
|---|---|---|---|
| 1 | Checks: the nightly jobs ran, the archive and the decision log are intact, no stop file is present. Note the start time and the **data cut-off** (the time of the newest data this session may use) | Script | 1 |
| 2 | Book what happened since the last session: fill earlier decisions at their opening price, update each fund's value, apply share splits and takeovers | Script | 2 |
| 3 | Screening: for every watched company, is there news since the last session that matters? Output: a short list | Screening agent | 7 |
| 4 | Deep analysis of at most **4 companies**: the analysts write or update one shared report per company, and record which catalysts have resolved | Analyst agents | 25 |
| 5 | Decisions: each AI fund's portfolio manager reads the reports and decides: buy, add, reduce, sell or do nothing, with a thesis | Portfolio managers | 38 |
| 6 | Risk limits checked; an order that breaks a limit is cut down or refused, and that is logged too. The two funds without AI make their moves. **The day's records are written and committed on the laptop: from here they are final** | Script | 40 |
| 7 | The readable day page is made; the day's files are checked for keys, addresses and long quotes | Script | 41 |
| 8 | The script publishes | Script | 42 |
| 9 | One-screen summary for when the owner looks again: what was decided, why, and how much usage the session took | Session | 43 |

**Time. Owner: a normal day takes 20-30 minutes, with a hard stop at 45.** No new deep analysis starts after
minute 20. Step 5 starts at minute 28 at the latest; a portfolio manager that has not finished at minute 38 is
stopped, and its fund gets a record "no decision today: out of time". Work that did not fit waits for the next
session. *Why a fixed stop:* it keeps usage predictable and the day light for the owner.

**Weekly and monthly extras run in the same session**, after step 8, so their timing cannot touch a decision: the
check on the screening (section 3) and the weekly summary in the first session of the week; the monthly letter and
the re-run of the universe in the first session of the month. On such a day the session makes at most 2 deep
analyses instead of 4, so that everything still ends within 45 minutes. An extra that does not fit moves to the next
session.

**Which companies get a deep analysis**, in this order: (1) companies a fund holds that have news; (2) other
companies the screening flagged; (3) companies with a catalyst on our calendar within 60 days, nearest first;
(4) the rest of the universe in rotation, so that every company gets a first report (about ten weeks for 200
companies). *Why:* holdings first, because a missed sell signal costs most.

**The owner's role in a session is to start it.** The owner does not change, add or block decisions. The leak
check before publishing (step 7) is not built twice: keys and addresses are caught by the check this repository
already runs on every commit and push, and only the check for long quotes is added. If it
finds something that may not be public (a key, an address, a long quote), that text is replaced by "[removed]" and a
correction record says so; the decisions themselves are published as they were committed in step 6. The owner sees
it in the summary and in the monthly review.

**The agents cannot look things up themselves.** Their agent files give them no web search and no web access. They
read only the files that the scripts prepared, all saved before the data cut-off. *Why:* this is what makes the
cut-off a fact instead of a promise.

Numbers (cash runway, dilution, position sizes, returns) are computed by scripts; agents read, argue and estimate
probabilities. *Why:* models make arithmetic mistakes; this is rule 7 of the research (`OPEN-SOURCE.md`, 3.5).

## 2. Skipped days, and the moment a decision counts

**Owner: sessions on working days, about 4-5 a week.** The rules below make sure that skipping a day, or choosing
the time of a session, can never be a way to pick results with hindsight.

1. **A day without a session is a day without trades**, for every fund, including the two without AI. They all carry
   the same handicap, so the comparison between them stays fair. The index funds simply run on.
2. **Nothing is caught up.** A sell rule that was triggered on a skipped day is acted on in the next session, at the
   next price, not at the price of the day it triggered.
3. **The fill day follows from the start time of the session**, which step 1 records before anything has been read:
   - started **before 14:00 Amsterdam time** on a US trading day, and published at least 30 minutes before the US
     market opens: filled at **that day's opening price**;
   - every other case (started later, published too late, a weekend, a US holiday): filled at the opening price of
     the **next US trading day**.

   The US market opens at 09:30 New York time, normally 15:30 in Amsterdam. For a few weeks a year the clocks differ
   (in March 2027 the US changes two weeks before Europe) and the open is at 14:30 Amsterdam time; the rule stays
   the same. A decision is therefore always published before the price it gets exists.
4. **A decision is final when it is committed in step 6**, and it counts as public when GitHub receives it. If
   publishing fails (no internet, GitHub down), the *same* commit is sent again later; the agents are never run again
   for that day. The time GitHub received it is read from GitHub afterwards and written into the first record of the
   next session, because the laptop's own clock proves nothing.
5. **One round of decisions per calendar day** (Amsterdam time). If a session crashes before step 6, it may be
   restarted once: it re-uses the reports that were already saved, runs only the steps that had not finished, and
   the log notes the restart. If that fails too, the day is a skipped day.
6. **Each record states its data cut-off**, and the agents can only read what was saved before it (section 1).
7. **History on GitHub cannot be rewritten:** the main branch is set to refuse rewrites of earlier commits. The
   decision record on the log (section 10) also weighs an independent public timestamp for the daily fingerprint.
8. **Skipped days are shown** in the track record, as a count per week.
9. **Stop file.** If a file named `STOP` exists in the data folder at step 1, no session runs and no fund trades.
   Creating it during a session does not cancel that session. Creating and removing it are logged. For emergencies
   only (a bug, a broken data source).

*Why the next opening price:* the free price data has one opening and one closing price per day, and the next
opening price is the first price nobody could have known when the decision was made.

**Weekends.** A weekend session is allowed only to make up for a working day skipped in that same week, and then
counts as that working day. Its decisions are filled at the next trading day's opening price. US market holidays are
not skipped days.

**How orders are booked** (details in decision record 0005):
- An order is a share of the fund's value (for example "3%"), turned into whole shares at the fill price.
- Sells are booked before buys. If cash is still short, all buys of that day are cut down by the same proportion.
- If a stock has no opening price that day (trading halted, common around big news), the order waits for the first
  day it has one, for at most 5 trading days; then it lapses and that is logged.

## 3. The agent team and its models

One shared analyst layer writes one report per company; only the decision layer differs per fund. *Why:* three funds
for the usage of about one and a half (`docs/IDEA.md`).

| Role | What it does | Model | Why this model |
|---|---|---|---|
| Screening | Reads the new filings, registry changes and news items of all watched companies; answers per company "worth a deep look today: yes or no, and why" | Haiku 5.5 | Hundreds of small reads a day. A miss is caught later by the rotation, and is measured (below) |
| Science analyst | The drug, its mechanism, the evidence so far, comparable drugs | Opus 5.5, high effort | Owner's preference; long documents |
| Clinical and regulatory analyst | Trial design, the main goal, what the regulator has said, base rates; states a probability for each coming catalyst | Opus 5.5, high effort | Same |
| Results reader | For every results announcement: was the main goal met, was the analysis planned in advance, is a subgroup being pushed forward | Opus 5.5, high effort | The clearest pattern in the case study (`CASE-FORENSICS.md`) |
| Financial analyst | Cash, runway against the next result, share sales, loan terms, warrants (numbers from script) | Opus 5.5, high effort | The "financing fine print" finding |
| Market analyst | Price history, market value against cash, what the price seems to assume, competitors | Opus 5.5, high effort | Same |
| Bull and bear researchers | Argue for and against, two rounds at most, in the Debate fund only | Opus 5.5, high effort | Same |
| **Portfolio manager** (one per AI fund) | Makes the sized decision and writes the thesis | **Fable 5.2**, the strongest model | Owner's preference: the most important role |
| Risk manager | Enforces the limits of section 4 | Script, no model | Limits belong in code, not in a prompt |

**Check on the cheap screening:** once a week one session lets Opus re-read a random sample of 20 companies that
Haiku marked "no". If Opus disagrees on more than 2 of 20 two weeks in a row, screening moves to a stronger model at
the next monthly review.

**How the exact model is logged.** Each agent is a file in `.claude/agents/` in this repository, with its model and
effort fixed in the file. Every log record stores, for each agent that contributed:
- the exact model name (for example `claude-opus-5-5`) and the effort level, read by script from the session's own
  record of each agent run, not from what a model says about itself;
- the fingerprint (SHA-256) of the agent file, and the git commit of the code;
- the Claude Code version.

A model or prompt change is therefore a new file version and visible in the log from that day on. If a model is not
available on a day, the session uses the next one down and the record says so; it does not silently substitute.

**Repeated decisions.** A decision to open a new position is made three times independently. The log records all
three; the position is opened only if at least two of the three say "buy", at the smallest size among those that do.
Forecasts are not repeated: the probability that is scored is the one in the analyst report. *Why:* a decision
that changes between runs deserves low confidence (`OPEN-SOURCE.md`, 3.5 rule 5). The pilot decides whether this fits
the usage limit; it is the second thing to go when scaling down (section 7).

**The full conversation of each session** (every prompt and answer) is copied at the end of the session into the
data folder outside the repository, because Claude Code removes its own copies after a while and because it
contains source text. Its fingerprint goes into the log, so it can be shown later to be unchanged.

To check in the pilot: that an agent file can really fix the effort level, and that the strongest model can be used
for an agent inside a session.

## 4. The universe, the funds and the baselines

### Universe
- **Who:** companies in the XBI fund, plus US-listed companies that file with the SEC under its pharma and biotech
  industry codes (2834, 2836).
- **Filter:** market value between $300 million and $10 billion, at least $2 million traded a day on average, share
  price at least $2. Expected: 150-250 companies.
- **Frozen with a date** at the start, re-run once a month (section 1, extras), every version kept. A company that
  drops out is no longer bought but may be held.
- Large pharma companies are context only (buyers, competitors), never bought.

*Why:* a list built from SEC codes also contains the companies that later fail, so it does not flatter the results,
and the floor on size and volume keeps out shares that cannot be traded at the quoted price (`DATA-SOURCES.md`, "Corporate actions and the universe").

### Rules for every fund
- Starts with **$1,000,000** paper money, in cash, on the same day. Long only (no bets on a fall). No borrowing.
- At most 25 positions. Cash earns nothing.
- **Same pool for all:** a fund, with or without AI, may only buy a company that has an analyst report (the
  "covered list"). *Why:* the analysts cover about four companies a day, so without this rule the funds without AI
  could invest everywhere from day one and the AI funds could not. In the weeks between the pilot and the start,
  sessions without trades write first reports, companies with a near catalyst first.
- **Brake:** a fund that has fallen 30% below its own highest value buys nothing more until the next monthly review.
- **Trading cost** per trade, the same for all five funds, charged on the amount traded: 0.25% for companies above $2 billion, 0.5% between
  $1 and $2 billion, 1.0% below $1 billion. These are starting figures; the pilot checks them against real price
  data and the decision record fixes them before the funds start. Returns are shown before and after costs.
- Trades smaller than 0.5% of the fund are not made (no fiddling).
- Share splits, takeovers and delistings are booked by script from SEC filings, by rules fixed in a decision record.

### The five funds
| Fund | Decision layer | Limits | What the comparison shows |
|---|---|---|---|
| **Careful** | One portfolio manager | At most 5% per stock; at most 3 positions with a make-or-break result (one that can halve or double the share price) within 30 days | Reference AI fund |
| **Bold** | One portfolio manager, same reports | At most 8% per stock; at most 8 such positions | Careful against Bold: the effect of risk appetite |
| **Debate** | Bull and bear researchers argue first, then the portfolio manager | Same as Careful | Careful against Debate: the effect of the debate |
| **Rules** (no AI) | Holds, in equal parts, the covered companies with at least 18 months of cash and a catalyst from a large final-phase trial or an FDA decision on our calendar within 6 months; nearest catalyst first, at most 20; re-drawn on the first session of each month | At most 5% per stock | What simple rules reach without any model |
| **Dice** (no AI) | 1,000 funds that each hold 20 random covered companies in equal parts, re-drawn on the first session of each month. The starting number of the random generator is published before the start, so the draws can be repeated by anyone | At most 5% per stock | The size of luck: where does each fund fall among 1,000 random ones? |

The exact rules of Rules and Dice are fixed in a decision record before the start, after the historical study has
given the base rates.

### Index funds for comparison
XBI, IBB and IWDA, bought on day one and held, computed from daily prices (only as far as the price source's
terms allow such figures to be published; decision record 0007). If the free price source does not carry
IWDA (it is listed in Europe), the US-listed fund on the same index is used and the track record says so. ARKG and
the specialist biotech investors appear as context in the monthly letter only. *Why:* their holdings arrive late or
may not be fetched automatically (`docs/decisions/0001`).

### What counts as the result (fixed before the start)
1. **Differences between funds:** each AI fund's place among the 1,000 Dice funds, and the difference between
   Careful, Bold, Debate and Rules, after costs. Shown twice: for the whole fund, and for the invested part only,
   so that a fund is not ranked by how much cash it happened to hold.
2. **Quality of the probabilities:** every thesis and every analyst report states a probability and a date for a
   checkable event ("the main goal of trial X is met, announced before 1 June"). When it resolves, a script scores it
   (Brier score: 0 is perfect, 0.25 is what always saying 50% scores) and compares it with the plain historical
   base rate for that kind of event. Analysts also give probabilities for catalysts of companies no fund buys, to
   reach 100 or more scored forecasts.
3. **Behaviour:** number of trades, cost drag, whether sell rules were followed, how often three repeated decisions
   agreed.

Returns against XBI, IBB and IWDA are reported, with the plain statement that six months cannot tell skill from luck.
The exact formulas and the rule for "fund X did better than fund Y" go into a decision record before the start.

### One formal side-hypothesis
Edits to a trial's registry record (a changed main goal, a completion date pushed back) are logged by script from
the nightly archive, and the price move over the next 30 days is compared with unedited trials. The measure is fixed
in the same decision record. *Why only this one:* it is the only thin-evidence signal we already collect.

### Left out of version 1
Option prices and paid data (**Owner: free sources only; a paid plan comes back at a monthly review only with a
concrete gap and a price**), newswires with unclear terms (company feeds and SEC filings only), transcribing
company calls, betting on falls, social media, patents, the CT Open challenge, non-US listings. "What is already
priced in" is estimated from market value against cash and from typical past moves (historical study).

## 5. The decision log and the track record

Everything public lives in one folder of this repository, `track-record/`:

```
track-record/
  log/2027/02/2027-02-03.jsonl     the decision log: one file per session day
  days/2027/02/2027-02-03.md       the same day as a readable page
  values.csv                       value of every fund and index, per day
  forecasts.csv                    every stated probability, its date, and the outcome once known
  weekly/2027-W06.md               weekly summary
  letters/2027-02.md               monthly letter to investors
  HEAD                             a small file: fingerprint and length of the log after the last session
```

### The log
- **Format:** JSON Lines (one record per line, plain text). Lines are only ever added at the end. Every record carries the fingerprint of
  the record before it, also across files, so a changed, removed or re-ordered record is detected. `HEAD` guards the
  newest end. This is the design of the archive (`docs/decisions/0001`) used again.
- **Kinds of record:** session start (start time, data cut-off, universe version, usage figures, the time GitHub
  received the previous day); forecast; decision; "no decision: out of time"; refused or reduced order; fill;
  outcome; correction; restart; stop file on or off.
- **A decision record holds:** the fund; the company; the action and the size; the thesis in a fixed form (claim;
  what we believe that others do not, and why; the catalyst and its expected date; the probability; the numbers;
  the risks; "we sell if..."); **what the agent saw** (for each source: its name, the date of the document, a link,
  and our own short summary); the model details of section 3; the data cut-off; the time.
- **Nothing is edited.** An outcome, a second thought or a found mistake is a new record that points to the old one.
- A script, `bobby-log verify`, re-checks the whole chain; it runs at the start of every session and can be run by
  anyone who copies the repository.

### What may and may not be in it
Only our own words and numbers. No files, tables or long quotes from any source; a quote is at most a sentence or
two, with its link. A trial fact names ClinicalTrials.gov and the date of the record, and says the wording is our
summary. No statements about named people that rest on allegations. Every page carries the line "paper money, not
investment advice". Each day's files are checked for keys, addresses and oversized quotes before publishing (section 1).

**Prices and lists from sources.** Our own results (fund values, returns in percent, scores) are published. Whether
single prices from the price service (fill prices, index values) may be shown is decided in record 0007 from the
service's terms, *before* the log format is fixed; if not, the public log shows returns only and the prices stay in
the data folder. The universe is published as our own list of company names; which companies are in the XBI fund is
never published.

### Publishing
| What | When | How |
|---|---|---|
| Log, day page, values, forecasts | End of every session | One commit, published at once; that moment is the decision time of section 2 |
| Weekly summary | First session of the week, after publishing | Written by script from the log |
| Monthly letter | First session of the month, after publishing | Section 8 |
| README "Track record" | Once, at the start | Links to `track-record/`; it holds no figures itself |

The daily publication goes straight to the main branch, made by a script that refuses to change anything outside
`track-record/` or to alter an existing line. The README sentence that "commit dates show that nothing was added
with hindsight" is replaced by the rules of section 2 (GitHub's receipt time, no rewriting of history).
*Why not a pull request per day:* the publication moment must be
immediate, and a daily pull request would be a chore. Code and documents keep the normal branch-and-pull-request
route. This exception needs a decision record (section 10).

## 6. Data streams to build, in order

The nightly archive stays as it is. Each stream below starts with reading the source's terms and `robots.txt`, noted
in a decision record, and saves its raw files in the data folder outside the repository.

| # | Stream | Why at this place |
|---|---|---|
| 0 | **Linking table**: company, SEC number, ticker, sponsor names in the trial registry, drug names, trial numbers. With a one-time check by the owner of about 200 matches | Nothing else works without it |
| 1 | **Daily prices** (Tiingo; Massive as a second source to cross-check and for share splits), saved raw every night | Needed for the universe filter, the fills and every value |
| 2 | **SEC filings**: event reports, share sales, insider trades, large-holder filings (with the edgartools library) | The best single source: free, official, permanently timestamped |
| 3 | **Trial-record changes**: compare each night's archived records with the day before | The data is already saved; only the comparison is new |
| 4 | **Quarterly reports**: cash, runway, and what changed in the wording since the last one | The best-supported overlooked signal |
| 5 | **Our own catalyst calendar**: expected results and FDA decision dates, taken from filings, every change dated | The funds are organised around catalysts; no open calendar exists |
| 6 | **Company news feeds** (the companies' own investor pages) | Fastest allowed news trigger |
| 7 | **Official confirmations**: FDA, Federal Register, EMA | Easy, official |

Streams 0-3 are needed for the pilot; 4-5 for the start of the funds; 6-7 may follow in the first live weeks.
Later, if a monthly review asks for it: short interest and interest rates, papers and preprints.

**The historical study** (README step 2) runs alongside the build, limited to two weeks of work, with its rules
written down before any data is looked at, on a complete list of past readouts instead of famous cases. It delivers
the base rates for section 4 and the typical size of price moves. It never scores the agents. It needs the AACT
copies, so AACT's terms are settled first.

Fetching happens in nightly timer jobs like the archive's, without any model. *Why:* a session should spend its
minutes on reading and deciding, not on downloading.

## 7. The pilot week

Five sessions on five working days on the real universe: the Careful fund alone on days 1-3, all three AI funds on
days 4-5 (the Debate fund uses the most, so it must be measured, not guessed). Pilot trades are logged in a
separate folder and do not count.

**Measured per session**
- usage, measured without the owner: a script counts the tokens of every model call per role from the session's
  own record (exact, per session). Where Claude Code makes the usage percentages available to scripts (its status
  line data), the script also records the five-hour and weekly percentages at the start and the end; the pilot
  checks this in its first session;
- minutes from start to end, and per step;
- number of agent runs per role, companies screened, companies analysed;
- how often the three repeated decisions agreed;
- the screening check of section 3.

**Limits. Owner: Bobby may use at most 25% of the weekly limit, and one session at most half of a five-hour limit.**
With five sessions a week that is about 5% of the weekly limit per session. Together with the 45 minutes these are the
project's hard caps; they take the place of a cap in money, because no money is spent on models. From the pilot
figures we work out what three AI funds would use.

**If the estimate for the full setup is above a limit, scale down in this order, one step at a time:**
1. at most 2 deep analyses a day instead of 4;
2. no repeated decisions;
3. two AI funds instead of three (Debate goes first: it uses the most);
4. the portfolio managers on Opus instead of the strongest model.

During the live run the same figures are logged every session. A week above 25% triggers the next step down at
once; two steps down without getting under the limit is a reason to stop (section 9).

**Turning tokens into percentages.** If the percentages cannot be read by script, the pilot ties tokens to the
limit once: the owner reads `/usage` a single time, at the end of the pilot week, and the script divides. From then
on the token count per week is the measure, and the owner looks at `/usage` only at the monthly review, as a check.
No per-session action is needed.

Only percentages are published; details of the owner's subscription stay out of the repository. The percentages are
approximate (the owner's other Claude use shares the same limits), so they are a guide, not an invoice.

After the pilot: a short report in `docs/`, the owner's go or no-go, then the funds start on a date announced in
the README at least a day before.

## 8. The fun layer (owner's wishes)

All three read only from `track-record/` and the price files; none can change a decision.

**The app. Owner: on the home network first.** A small read-only web page on the home server, reachable at home
and on the owner's phone through the existing private connection; nothing is opened to the internet. Making it
a public page later is a separate decision for the owner. What it shows, game-style:
- a league table of the five funds and three index funds, with each AI fund's place among the 1,000 Dice funds;
- per fund: the positions as cards with the thesis in two lines, the next catalyst and a countdown;
- a "calls" page: every forecast, and hit or miss once resolved, with a running score per analyst role;
- a calendar of coming catalysts; the latest letter; the days without a session.

**The monthly letter to investors. Owner: in the repository and the app, plus a phone message with the link.**
Written once a month, in the first session of the month after publishing, by the three portfolio managers, one page each, in plain language: what
we did, what went right and wrong, what we expect next month. Followed by a fixed table part made by script. It is
also the report for the monthly review.

**Alerts. Owner: holdings only.** Two kinds of phone message, both made by a script, not by a model:
- **A big move:** a stock that a fund holds moved 20% or more in a day. Sent by the nightly price job, so it arrives
  the morning after. No session is open at night, and none is needed.
- **A catalyst resolved:** sent at the end of the daily session in which the analysts recorded the outcome.

Each message says **expected or not**: the script compares it with what was logged beforehand. "Expected: Careful's
thesis of 3 February named this result for this week and gave it 60%"; or "Not expected: no thesis mentions an event
now".

## 9. The monthly review, and when we stop

**Review:** the first weekend of each month, about 45 minutes, in a normal session run as a short interview that a
non-expert can lead. Agenda:
1. the letter: what the funds did, in plain words;
2. what was missed (big moves marked "not expected", forecasts that failed badly);
3. usage against the limits, skipped days, failed jobs;
4. any breach of the rules, and the result of `bobby-log verify`;
5. what to change. Changes apply from that day forward only, are added to this document under "Changes" with the
   date, and a changed fund gets a version mark in the track record;
6. is it still fun and instructive?

**End. Owner: 26 weeks from the start, then a final report and the owner's decision** to stop, continue or start a
version 2. The experiment stops earlier when:
- a core rule is broken beyond repair: a published decision was edited, or information from after a data cut-off
  reached a decision and cannot be isolated;
- usage stays above the limit after two steps down;
- fewer than half of the working days had a session (make-up weekend sessions included), two calendar months in a row;
- the owner says so at a review.

A stop is logged; the track record stays published as it is.

## 10. Decisions that need a decision record

Written with the design-decision skill after the owner has approved this document, each with options compared and
sources. Numbers continue after `0002`.

| # | Decision | Needed before |
|---|---|---|
| 0003 | How the agents run: sessions opened by hand, the skipped-day rules and the decision moment of section 2 | Any agent code |
| 0004 | Decision log: record format, fingerprint chain, folder layout, daily publication straight to the main branch, protection against rewriting, an independent public timestamp (for example OpenTimestamps, open source) | Any agent code |
| 0005 | Paper funds: where the books are kept (replayed from the log, or a small database), how orders are booked, trading costs, splits and takeovers | Pilot |
| 0006 | Universe and linking table: sources, filter, how matches are stored and checked | Stream 0 |
| 0007 | Price source: terms of Tiingo and Massive, what is saved, what may be published | Stream 1, and before 0004 is final |
| 0008 | SEC filings: access rules, the contact address kept in a local file, the library | Stream 2 |
| 0009 | Agent team: roles, models, how model and prompt versions are logged, repeated decisions | Pilot |
| 0010 | Scoring: the formulas, the rules of the Rules and Dice funds, the registry-edit hypothesis | Start of the funds |
| 0011 | Catalyst calendar and company news feeds: how dates are taken from filings; terms per feed | Streams 5-6 |
| 0012 | The app: how it is built and served on the home network (recorded with the home server's decisions, with a pointer here) | Building the app |
| 0013 | Alerts and letter: thresholds, wording rules, message channel | Building them |
| 0014 | AACT: terms for downloading the dated registry copies | Historical study |

## Order of work

1. Decision records 0003-0008, then streams 0-3. Alongside: the historical study (after 0014).
2. Agent files, the log and the fund books (0005, 0009); the pilot week.
3. Streams 4-5, record 0010, first reports for the covered list, the owner's go; the funds start. Aim: pilot in January 2027, start in February 2027.
4. In the first live weeks: streams 6-7, the app, alerts, the first letter.

## Words used
- **Agent**: one run of a Claude model with a fixed role and instructions.
- **Session**: one conversation in Claude Code, opened by the owner with one command.
- **Catalyst**: a dated event that can move a share price a lot, such as a trial result or an FDA decision.
- **Thesis**: the written reasoning for a position, in a fixed form.
- **Data cut-off**: the time of the newest information a session may use.
- **Fill**: the price at which a paper trade is booked.
- **Fingerprint (SHA-256)**: a short code computed from a file; any change to the file changes the code.
- **JSON Lines**: a plain text file with one record per line.
- **Brier score**: a measure of how good stated probabilities were; lower is better.
- **Base rate**: how often something happened in the past, for example how often large final-phase trials succeed.
- **Covered list**: the companies that have an analyst report; only these can be bought.
- **Make-or-break result**: a result that can halve or double a share price in a day.
- **Runway**: how long a company's cash lasts at its current spending.
- **XBI, IBB**: US biotech index funds. **IWDA**: a world index fund, the "do nothing" comparison.
- **Decision record (ADR)**: a short document in `docs/decisions/` that records one design choice and why.

## Changes
None yet.
