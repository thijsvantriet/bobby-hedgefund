# Pilot report, November 2026 (draft)

Status: **draft**. The figures for all three AI funds are **open** until the two extra pilot days have run
(Monday 2026-11-30 and Tuesday 2026-12-01). The owner's go or no-go follows this report (spec, section 7).

Paper money only. Pilot trades do not count, and nothing here is investment advice.

## In short
- Five rounds ran on five working days (2026-11-23 to 27), **all with the Careful fund only**. The spec wanted
  all three AI funds on days 4 and 5; they were not started in time, so the full setup is not measured yet.
- A Careful-only round takes **3 to 5 minutes** of its 45 and about **4 million tokens**, mostly read from the
  cache. It uses **5 to 7% of a five-hour limit** and **less than 1% of the weekly limit** (day 5: 19% before and
  after the round). Both are far below the caps (half a five-hour limit, about 5% of the week per round).
- The agents ran on the models and efforts of their files every time. 93 of 97 answers were used; the four that
  were thrown away all had causes that are now fixed.
- The agents most often missed the **trial registry records themselves** and **basic company documents**. The
  second is partly fixed (recent filings are now in the folder); the first is the main proposal before go-live.
- Estimate for three funds: about **twice** the Careful-only use, so roughly 10 to 16% of a five-hour limit and
  about 2% of the week per round. To be measured on the extra days.

## Usage per round
From each round's `usage.json` (the session's own records; tokens are exact, percentages are the account's and
include the owner's other Claude use at the same time).

| Day | Date | Minutes | Agent runs | Answers used | Companies with news / judged / flagged / analysed | Forecasts | Orders | Tokens (million) | Five-hour % at end | Week % start → end |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 11-23 | 5 | 12 | 11 | 4 / 4 / 1 / 2 (a weekly day: at most 2) | 9 | 1 buy | 2.6 | 5 | ? → 30 |
| 2 | 11-24 | 4 | 23 | 23 | 11 / 11 / 5 / 4 | 33 | none | 4.2 | 7 | ? → 34 |
| 3 | 11-25 | 5 | 20 | 20 | 23 / 23 / 10 / 4 | 25 | 1 buy | 4.1 | 7 | 34 → 51 * |
| 4 | 11-26 | 4 | 22 | 20 | 28 / 3 / 3 / 4 (25 lost, see faults) | 15 | none | 4.4 | 6 | ? → 1 (new week) |
| 5 | 11-27 | 3 | 20 | 19 | 1 / 1 / 1 / 4 | 18 | none | 3.8 | 5 (from 0) | 19 → 19 |

\* Other Claude sessions of the owner ran in the same minutes, so
this jump is not the round's alone. "?" = no figure at the start: Claude Code gives the percentages to the status
line only after the first model call of a session, so the start of a fresh session often has none. The token
count per role is therefore the exact measure, and the percentage at the end the guide.

**Minutes per step** (averages over the five days): checks and preparation 0.1, screening 0.4, deep analysis 1.6,
decisions (three manager runs) 1.6, everything after that under 0.2. No step came near its time limit.

## Usage per role
Totals over the five rounds; tokens per round are averages.

| Role | Model, effort | Runs | Used | Seconds per run | Tokens per round (million) | Output per round (thousand) |
|---|---|---|---|---|---|---|
| Portfolio manager, Careful (3 runs a day) | Fable 5.2, high | 15 | 14 | 73 | 1.22 | 21 |
| Leading session (runs the commands) | as opened | – | – | – | 0.93 | 5 |
| Science analyst | Opus 5.5, high | 18 | 18 | 55 | 0.42 | 19 |
| Clinical and regulatory analyst | Opus 5.5, high | 18 | 17 | 51 | 0.40 | 17 |
| Financial analyst | Opus 5.5, high | 18 | 17 | 51 | 0.35 | 18 |
| Market analyst | Opus 5.5, high | 18 | 18 | 48 | 0.35 | 17 |
| Screening | Haiku 5.5, low | 6 | 5 | 15 | 0.07 | 4 |
| Results reader | Opus 5.5, high | 4 | 4 | 32 | 0.05 | 2 |

The managers are the biggest single user: each run reads every report of the day. Most tokens are cache reads.

## The three repeated decisions
Each day the Careful fund's manager ran three times; a new position needs two of three.

| Day | Run 1 | Run 2 | Run 3 | Result |
|---|---|---|---|---|
| 1 | buy Vir 2% | buy Vir 2% | buy Rezolute 2% | Vir bought (2 of 3); Rezolute not (1 of 3) |
| 2 | nothing | nothing | nothing | all three agree |
| 3 | nothing | buy Rezolute 2% | buy Rezolute 1.5% | Rezolute bought at 1.5% (2 of 3, smallest size) |
| 4 | nothing | thrown away (fault 6) | nothing | two readable runs, both nothing |
| 5 | nothing | nothing | nothing | all three agree |

On 3 of 5 days the three runs agreed fully, every time on doing nothing. Each of the two buys had a dissenting
run. Too few days to judge the rule; it worked as designed and cost about a third of the round's tokens.

## The weekly check on the screening
**Open.** It did not run in the pilot week: the agent file existed, but the check was not part of the round
(day 1 was a "weekly" day and nothing happened). It is now built and runs on Monday 2026-11-30, on the 20
companies the screening passed over from 23 to 27 November (exactly 20 to draw from).

## What the agents missed without web access
The agents list what they lacked in every answer: 555 lines over the five days. Grouped roughly by theme:

| What they missed | Lines | Now |
|---|---|---|
| The trial registry records themselves (design, main goal, patients, dates) | 111 | **Proposal 1** below |
| Company basics: annual and quarterly reports, pipeline, how a drug works | 98 | Partly fixed: recent filings (90 days) are now in the folder |
| Filings behind our earlier reports, citable by today's number | 45 | Fixed |
| Documents of the regulator (FDA letters, labels, meeting minutes) | 42 | Only what a company files; not planned |
| An earlier report of ours (none existed yet for a first analysis) | 41 | Goes away as coverage grows |
| Competitors, papers, medical literature | 26 | Papers are a source in the spec, not built |
| A current market value | 15 | Fixed (worked out from the shares and the last close, private) |
| Press releases and presentations that were not filed | 14 | Not planned |
| The universe list [1] and the linking table [3] | 7 | Fixed (the company's own lines are in its folder) |
| Other (details of insider sales, trading plans, deal terms, ...) | 156 | Mostly specific; see proposal 3 |

## Faults and what was done
| # | Fault | Days | Done |
|---|---|---|---|
| 1 | Universe list [1] and linking table [3] listed as sources, but not in the folder | 4, 5 | Fixed: each company's own lines are in its folder (record 0003, update 2026-11-27) |
| 2 | Filings from earlier sessions not in the day's list, so not citable; an earlier report's [n] pointed at other filings | every day | Fixed: earlier filings of the last 90 days for companies that may be analysed, and a note with today's numbers above a copied report |
| 3 | A whole analyst section thrown away for a forecast without `sources` | 5 | Fixed: a missing list counts as empty |
| 4 | Six forecasts refused as "defined by a price"; all six were company events ("shares sold *under* the agreement") | 2, 4, 5 | Fixed: the check needs a figure after "over/under/at least/at most"; a replay over all pilot forecasts changes exactly these six |
| 5 | 5 to 26 refused searches a day, mostly from the session folder itself | every day | Instructions now say where to search |
| 6 | A manager run thrown away because it had *tried* to read Claude Code's saved copy of a long search result (the read was refused) | 4 | Fixed: a refused read no longer counts against the answer |
| 7 | A screening answer without its block of JSON: 25 companies not judged | 4 (and day 0) | Fixed: one fresh run of such a batch |
| 8 | 22 of 100 forecasts repeated an open one word for word | 2-5 | Fixed: an unchanged repeat is not written again |
| 9 | The weekly check on the screening never ran | 1 | Built; first run 2026-11-30 |
| 10 | 7 of the 202 companies have no linked trials, among them Rezolute, which the Careful fund holds | – | Proposal 2 |
| 11 | An analyst's text after its block of JSON | 1 | Fixed on day 1 (PR #31) |

## Proposals (not built)
1. **The trial records in the company folder.** For each linked trial, the key fields of its newest saved record
   (phase, status, main goal, number of patients, dates), cited by number. The most-missed information of the
   pilot. Recommended before go-live.
2. **The by-hand check of missed sponsor names**, already on the plan, starting with the 7 companies without any
   linked trial (Rezolute first). Recommended before go-live.
3. **Insider filings in full.** The reader of insider trades leaves out the footnotes, where a filing says
   whether a sale was under a pre-arranged trading plan or covered tax; agents asked for this a dozen times. Small.

## Open until the extra days (30 November and 1 December)
- Usage per round and per role with all three AI funds (Careful, Bold, Debate), above all the Debate fund's bull
  and bear runs: **open**.
- Minutes per round with three funds: **open**.
- Agreement of the repeated decisions for three funds: **open**.
- The first weekly check on the screening: **open**.
- Whether the fixes hold in a real round (fewer refused searches, no lost answers for these causes): **open**.
- Estimate before measuring: about twice the Careful-only use (two more sets of three manager runs, and per
  analysed company two bull and two bear runs), so roughly 8 to 9 million tokens, 10 to 16% of a five-hour limit
  and about 2% of the week per round, in about 8 minutes. If the measured figure is above a cap, the spec's order
  of scaling down applies (section 7).

## Go or no-go
**Open**, for the owner, after the extra days.
