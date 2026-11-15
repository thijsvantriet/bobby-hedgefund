# Research summary in plain language

Night of 2026-11-15. Full reports: [OPEN-SOURCE.md](OPEN-SOURCE.md) (what to reuse),
[DATA-SOURCES.md](DATA-SOURCES.md) (which information to collect), [CASE-FORENSICS.md](CASE-FORENSICS.md) (what past cases teach).
Everything below is a proposal for the spec interview. Nothing is decided and nothing was built or installed.

## Key findings

1. **We should build the core ourselves and borrow designs.** Two good open-source "AI hedge fund" projects exist, but each
   breaks one of our rules: TradingAgents rewrites its decision log afterwards, and ai-hedge-fund runs on a paid data service.
   Nobody has published an open biotech-specific agent fund, so that part is still new.
2. **Nobody has shown that AI agents beat the market.** Every clean test is short, uses a handful of large stocks and ignores
   trading costs. Tests on historical data look good only because the models remember what happened. This confirms the
   project's forward-only rule and tells us what to measure.
3. **Six months cannot prove skill from returns.** Beating XBI by 10% would be within the range of luck. Six months *can* show
   clear differences between fund setups, how the agents behave, and whether their stated probabilities are any good. That
   last one needs every thesis to state a probability and a date.
4. **Company filings at the US securities regulator (SEC) are the best single source.** Free, official, and every document
   has a permanent timestamp. Results, share sales, insider purchases, executive departures and delisting warnings all
   appear there.
5. **Many sources erase their own past.** The trial registry's data service only gives today's version of a trial record;
   fund holdings, exchange lists and company pipeline pages are overwritten daily. What we do not save from day 1 is lost.
6. **The valuable overlooked information is not exotic.** It is the financing fine print (how long the cash lasts against the
   next result, loan conditions, warrants), wording that changes between two quarterly reports, and the inspection record of
   the factory that makes a drug awaiting approval. Reading and comparing long documents is where agents are strong.
7. **The hardest practical job is linking the data**: knowing that a trial sponsor name, a stock ticker, a drug code and a
   paper all belong to the same company. No open dataset does this.
8. **Looking back at 14 past cases: the warning signs were mostly not missed.** They were public and moved the price the
   day they appeared. Where investors went wrong was in believing the rescue afterwards (a failed trial "re-analysed" into a
   success). A few patterns did come before failures and not before successes: a missed main goal dressed up with subgroup
   analyses, integrity problems around the founding science, a troubled manufacturing site, and an effect that shrinks as
   more patients are reported. Several famous warning signs (short-seller reports, cancelled FDA meetings, a partner
   walking away) appeared just as often before good outcomes. Fourteen hand-picked cases prove nothing; they give the
   proper historical study its hypotheses.
9. **Much is closed.** No free price source is fully clean; X, Reddit and StockTwits need payment or approval; ready-made FDA
   calendars and call transcripts are paid products with restrictive terms.

## Recommended stack (proposal)

| Part | Choice | Open? |
|---|---|---|
| Language and environment | Python with uv, Docker Compose, systemd timers | Open |
| Agent team | Our own small orchestrator on the Anthropic software kit; team structure copied from TradingAgents | Our code; Claude itself is closed and paid |
| Decision log | Our own, tamper-evident: each record carries a fingerprint of the previous one (design from ai-hedge-fund) | Our code |
| Cost control | Our own token ledger with a hard monthly stop | Our code |
| Paper portfolio | Our own small ledger in SQLite or DuckDB | Open |
| Performance statistics | empyrical-reloaded, QuantStats | Open |
| SEC filings | edgartools | Open |
| Trial registry, FDA, EMA, papers | Their official data services, called directly | Official open data |
| Prices | One free-tier commercial service | **Closed**, personal-use terms |
| Not used | LangChain, OpenBB, trading engines, paid calendars and transcripts, social-media services | - |

## First data streams (proposal)

1. SEC filings: event reports, share sales, insider trades, large-holder filings.
2. Daily copies of trial records, compared by script.
3. Daily closing prices, saved raw.
4. Quarterly reports: cash, runway, and what changed since the last one.
5. Our own calendar of FDA decision dates and expected results, with every change recorded.
6. Company news feeds.
7. The files that define the universe and the benchmarks (XBI and ARKG holdings, exchange lists).
8. Official regulatory confirmations (FDA, Federal Register, EMA).
9. Short interest, borrow fees and interest rates.
10. Papers and preprints, plus a calendar of conference abstract releases.

On top of streams 1 and 6, the case study argues for one cheap addition: an agent that reads every results announcement for
*quality* (main goal met or missed, planned or after-the-fact analysis, corrections).

Before any of these: the linking table, with a one-time check by you of about 200 company matches.

**Worth starting before the spec is finished:** a small script that only saves the files that are overwritten daily.

## Open questions for the spec interview

**Needed before any code runs**
1. Which contact e-mail goes into requests to the SEC? It is mandatory. A separate project address is suggested.
2. May the public repository show only our own results, short quotes and official data, never raw commercial data?
3. Which free sign-ups are acceptable (a price service; optionally several official services)?
4. Start the day-1 archive now, and where should it be stored and backed up?

**Shaping the experiment**
5. What exactly is the experiment's main result: returns, differences between setups, or the quality of the probabilities?
   The research points to the last two.
6. Which baselines: XBI, IBB, IWDA, the rule-based fund, and a random-pick fund run many times?
7. How many times should a decision be run to measure its consistency, given the token budget?
8. Do we run the proper historical study (step 2 in the README) the careful way: rules written down first, a complete list
   of past readouts instead of famous cases, matched comparisons? It needs SEC access.
9. Which thin-evidence signals become formal hypotheses, with the measure fixed in advance (registry edits, pipeline-page
   changes, specialist-fund moves)?
10. What trading cost do we charge for small companies?
11. How do we estimate "what is already priced in" without paying for options data?

**Scope**
12. Company calls: transcribe public webcasts ourselves, or leave them out of version 1?
13. Newswires: company feeds and SEC only, or also the newswire feeds whose terms are unclear?
14. Should the clinical analyst also enter CT Open, the public trial-prediction challenge, as a side test?
15. Is a small paid data plan (about $20-30 a month) acceptable later, for example for delisted companies or options?

## Corrections to our earlier notes
[IDEA.md](../IDEA.md) said the two main frameworks only work on historical data; both now run forward. It also overstated two
research papers and gave a data licence that belongs to the paper. Details in [OPEN-SOURCE.md](OPEN-SOURCE.md) section 2.
IDEA.md itself was left unchanged.

## How this was done, and assumptions made while you slept
- Seven research agents (Opus), each on one narrow topic. Their raw notes are in [notes/](notes/). I re-checked the claims that carry a recommendation against the
  original source and repeated the key test calls myself.
- Beyond the brief, as you asked: a section on overlooked streams, a forensic look at past cases, the point-in-time question
  for every source, the linking problem, and a sceptical reading of the evidence.
- Sources that require an e-mail address in the request (SEC, PubMed and others) were **not** tested. Only anonymous public
  services got a tiny test call.
- No decision record was written: these reports feed decisions, they are not decisions.
- Nothing was added to the Home TODO list. Proposed items: the four "needed before any code runs" questions above.
- Events dated after mid-2026 (policy, FDA leadership) come from the linked sources only and are marked for confirmation.

## What is uncertain
- Terms of use of several sources could not be read and are marked "unverified" in the reports.
- Volumes and token costs are estimates until the pilot week.
- Much of the evidence on AI trading agents is not peer-reviewed.
- This is research for a paper-money experiment, not investment or legal advice.
