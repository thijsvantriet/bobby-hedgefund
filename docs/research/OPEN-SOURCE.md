# Open-source landscape: what to reuse, what to build

Research night of 2026-11-15 (brief: [BRIEF.md](BRIEF.md)). Plain-language one-pager: [SUMMARY.md](SUMMARY.md).
Everything here is input for the spec session. Nothing is decided.

**How to read this**
- Repository numbers (licence, stars, last commit, releases) come from the GitHub API on 2026-11-15. Licences were read from the
  LICENSE file, not the README badge.
- **[checked]** = I re-checked the claim myself against the primary source after the research agents reported.
  No tag = reported by a research agent with a link, not re-checked by me. **[unverified]** = no primary source found.
- "Open source" means an OSI-approved licence. "Source-available" means you can read the code but the licence restricts use.
  "Closed" means proprietary.
- **[checked]** covers repository facts (licence file, last commit, release, the quoted code behaviour). It does not mean I
  re-read every paper.
- No code was cloned or run. Nothing was installed. This is research for a paper-money experiment, not investment advice.

## 1. The short version

1. **No existing project fits our rules, so the recommendation is to write a small orchestrator ourselves and borrow designs.**
   The two serious frameworks (TradingAgents, ai-hedge-fund) are well made but clash with at least one of our rules:
   one rewrites its decision log, the other depends on a paid data service. No open biotech-specific agent fund was found.
2. **The evidence that LLM agents can beat the market is weak.** No clean forward study shows it after trading costs.
   This is not a reason to stop (the project is an experiment), but it changes what we should measure: section 3.
3. **Four corrections to our own notes in [IDEA.md](../IDEA.md)**: section 2.
4. **None of the trading/backtesting engines is worth installing.** A small ledger of our own is simpler and more transparent.
5. **The hard, unglamorous part is linking the data** (stock ticker ↔ SEC company number ↔ trial sponsor name ↔ drug code ↔
   trial number). No open dataset does this. It is the piece we really have to build.
6. **Several popular tools look open but are not** (vectorbt, PyBroker, ArcticDB, parts of TradingAgents-CN, AI-Trader):
   section 8.

## 2. Corrections to docs/IDEA.md

| IDEA.md said | What the sources say |
|---|---|
| TradingAgents and ai-hedge-fund are "backtest-only" | Out of date. TradingAgents has a headless mode for scheduled runs. ai-hedge-fund v2 has forward paper trading (`aihf paper run`) with a hash-chained ledger. **[checked]** ([ledger.py](https://github.com/virattt/ai-hedge-fund/blob/main/hedge_fund/paper/ledger.py)) |
| Look-Ahead-Bench: "most agents fail after their knowledge cutoff" | Too strong. It is a one-author proof of concept on 5 tech stocks. Standard open models lose 15-22 percentage points of outperformance after their cutoff; the commercial "point-in-time" models the paper promotes do not ([arXiv 2601.13770](https://arxiv.org/abs/2601.13770)). Weak evidence, right direction. |
| StockBench: "risk-adjusted gains but not total-return wins" | Muddled in the paper itself. Returns range from -2.8% to +2.5% against +0.4% for buy-and-hold over 4 months, 3 runs, no trading costs ([arXiv 2510.02209](https://arxiv.org/abs/2510.02209)). Fair reading: no meaningful edge either way. |
| CT Open is "CC BY 4.0" | That is the licence of the paper. The licence of the CT Open data could not be verified. Check on [ct-open.net](https://ct-open.net/) before reusing anything. |

## 3. What the evidence says about LLM trading agents (the sceptical part)

This section matters more than the framework comparison, because it decides what the experiment can and cannot show.

**3.1 No clean study shows LLM agents beating a passive benchmark after costs.**
Every forward or after-cutoff study found is short (2 weeks to 4 months), uses 5-20 large liquid stocks, runs each model one to
three times, and ignores trading costs. Within those limits, results are a few percent either way and flip between rising and
falling markets.

| Study | Setup | Result | Limits |
|---|---|---|---|
| FINSABER ([arXiv 2505.07078](https://arxiv.org/abs/2505.07078), KDD 2026) | 20-year backtests of two published agents on a survivorship-free S&P 500 | No significant outperformance; buy-and-hold beats both tested agents significantly. Agents too cautious in rising markets, too aggressive in falling ones | Backtest, so models may remember |
| Profit Mirage ([arXiv 2510.07920](https://arxiv.org/abs/2510.07920)) | Five published frameworks, same test before and after the model's cutoff | Returns fall 50-72% after the cutoff. Models recall "did the market rise on day X" with 85-93% accuracy | Preprint |
| StockBench ([arXiv 2510.02209](https://arxiv.org/abs/2510.02209)) | 20 Dow stocks, 4 months after cutoff | -2.8% to +2.5% vs +0.4% buy-and-hold | 3 runs, no costs |
| DeepFund ([arXiv 2505.11065](https://arxiv.org/abs/2505.11065), NeurIPS 2025) | Live, 5 stocks | Most models lost money | Tiny universe |
| LiveTradeBench ([arXiv 2511.03628](https://arxiv.org/abs/2511.03628)) | Live, 21 models, 10 weeks | General model quality does not predict trading results (correlation about 0.05 for stocks, -0.38 on prediction markets) | No costs, no baseline |
| AI-Trader ([arXiv 2512.10971](https://arxiv.org/abs/2512.10971)) | Live, 6 models, ~5 weeks | Mixed; one model adopted a single news story's thesis without checking | No costs |
| Nof1 Alpha Arena | Real money, crypto then US stocks | Wildly mixed | Closed; press coverage only **[unverified]** |
| CT Open ([arXiv 2604.16742](https://arxiv.org/abs/2604.16742), COLM 2026) | Predicting trial outcomes, live windows | Claude Opus 4.5 scores 70.2 (macro-F1, a 0-100 accuracy measure) on a window it may have seen and 53.7 on a clean one. A plain statistical model stays near 66 on both | The only biotech-specific live benchmark |

**3.2 Failure modes that recur across independent studies**
- Remembered outcomes. This is why our forward-only rule exists, and the evidence supports it strongly. It also applies to
  examples: a famous past biotech case shown to an agent "as if open" is contaminated.
- Too cautious in rising markets, too aggressive in falling ones.
- Overreaction to headlines and overtrading, worse in "reasoning" models.
- Blindness to trading costs. Small biotechs have much wider spreads than the large stocks used in these studies.
- Trusting a single source; arithmetic and output-format errors.
- Large run-to-run variation. In StockBench, changing only the number of stocks swung one model from -4.6% to +3.2%.

**3.3 Forecasting research adds two useful points.** In live forecasting tournaments the best systems now come close to expert
human forecasters, though that claim is disputed ([FRI](https://forecastingresearch.substack.com/p/ai-models-have-likely-reached-parity),
[Good Judgment's reply](https://goodjudgment.substack.com/p/not-so-fast)). The top entries average several runs, and combining several separate bots helped, with no further gain
beyond about 10 bots ([Metaculus results](https://www.lesswrong.com/posts/wZBbDqzfBjYG58CxK/futureeval-spring-results-pros-beat-bots-but-the-gap-is)).
And models still lag market prices close to an event ([Prophet Arena](https://arxiv.org/abs/2510.17638)). So the market price is
a strong starting estimate, and claims that "we know better" should be rare and well argued.

**3.4 What six months can and cannot show** (a rough estimate by the research agent, not from a paper).
A portfolio of 20-30 small biotechs will typically differ from XBI by 20-30% a year through luck alone. To be statistically
distinguishable from luck, a setup would need to beat XBI by roughly 30-40 percentage points in six months. So:
- Six months **cannot** prove skill from portfolio returns. Beating XBI by 10% is consistent with luck.
- Six months **can** show large differences between fund setups, because they share the same analysts and the same market,
  which cancels much of the noise.
- Six months **can** show behaviour: trading frequency, cost drag, whether exit rules were followed.
- Six months **can** show whether the agents' probabilities are any good, if every thesis states a probability and a date.
  With 100+ resolved catalysts this is the most informative output of the project.

**3.5 Design rules that follow** (proposals for the spec)
1. Agents only see documents with a timestamp of when they became public; log the IDs of what was seen.
2. The decision log is append-only and tamper-evident. Outcomes and reflections are new records pointing to the decision.
3. Charge realistic small-cap trading costs and report returns before and after costs.
4. Baselines: XBI, IBB, IWDA, the rule-based setup, and a random-pick baseline run many times, so luck has a visible size.
5. Where affordable, run a decision 3-5 times and record the spread. Wide disagreement means low confidence.
6. Risk limits live in code, not in a prompt (maximum position, maximum number of binary readouts at once, drawdown stop).
7. Numbers are computed in code (cash runway, dilution, valuation). The model argues and estimates probabilities.
8. Score probabilities (Brier score) against base rates, not only profit and loss.
9. Token budget enforced in code with a hard stop; report results per dollar of tokens.
10. Fix the comparison metrics and the rule for "setup X is better" in the spec before going live.

**3.6 How each benchmark guards against look-ahead, and whether we could join or reuse it**

| Benchmark | Guard against look-ahead | Open? | Join or reuse? |
|---|---|---|---|
| StockBench | Test window lies after the models' cutoffs | Code [Apache-2.0](https://github.com/ChenYXxxx/stockbench), dormant | Reuse its metrics; not live |
| FINSABER | Point-in-time data, no survivorship bias; admits models may still remember | [Apache-2.0](https://github.com/waylonli/FINSABER), active | For the lesson on market regimes; never to score agents |
| Look-Ahead-Bench, Profit Mirage | Compare the same agent before and after its cutoff | Code without licence / preprint | Evidence only |
| DeepFund | Live data after the cutoff | [MIT](https://github.com/HKUSTDial/DeepFund) | Design reference |
| LiveTradeBench, AI-Trader | Live; tools filtered by time | PolyForm Noncommercial / no licence file | No |
| [Agent Market Arena](https://arxiv.org/abs/2510.11695) | Live; finds the framework matters more than the model | [MIT](https://github.com/The-FinAI/Agent_Market_Arena) | Possibly; whether submissions are open was not checked |
| [InvestorBench](https://aclanthology.org/2025.acl-long.126/) | None: historical backtests | MIT, dormant | No |
| [ForecastBench](https://www.forecastbench.org/) | Only questions still unresolved at forecast time | [MIT](https://github.com/forecastingresearch/forecastbench), open tournament | Possibly, as a side test of probability quality |
| Metaculus AI benchmark | Live questions | Open tournament | Possible, off-topic |
| [FutureX](https://arxiv.org/abs/2508.11987), Prophet Arena | Live daily questions / live events | Papers | No. FutureX: experts beat agents on most tiers **[unverified detail]** |
| **CT Open** | Scores only trials whose results first became public inside the test window | Open submissions; data licence **[unverified]** | **Yes, as an optional side test** for the clinical analyst |
| TOP / HINT | None: historical trials the models have seen (agent's inference) | Non-commercial agreement | Only for non-AI baselines |

## 4. Multi-agent LLM trading frameworks

| Project | Licence | Stars | Last commit | Claude support | Runs forward? | Decision log | Verdict |
|---|---|---|---|---|---|---|---|
| [TradingAgents](https://github.com/TauricResearch/TradingAgents) | Apache-2.0 **[checked]** | 122.7k | 2026-11-04, v0.7.1 **[checked]** | Yes, native | Yes, headless mode | Markdown file, **rewritten when outcomes are added** **[checked]** | Borrow the design |
| [ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) | MIT **[checked]** | 64.7k | 2026-11-09, v2.7.2 **[checked]** | Yes, default | Yes, `aihf paper run` | Hash-chained append-only files **[checked]** | Borrow the design; data layer is a paid service |
| [FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) | Apache-2.0 **[checked]** | 8.4k | 2026-10-24 | Not verified | No, writes reports | Report files | Borrow one principle |
| [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) | MIT | 21.6k | 2026-10-25 | No | No | - | Ignore: fine-tunes other models |
| [FinMem](https://github.com/pipiku915/FinMem-LLM-StockTrading) | MIT | 1.0k | 2024-08 | No | No | - | Ignore: abandoned |
| [FinAgent](https://github.com/DVampire/FinAgent) | MIT | 78 | 2024-08 | No | No | - | Ignore: abandoned, 5+ paid data keys |
| [FinCon](https://github.com/The-FinAI/FinCon) | MIT | 73 | 2026-10 | - | - | - | Ignore: code never released |
| [AI-Trader](https://github.com/HKUDS/AI-Trader) | **No licence file** | 23.3k | 2026-06 | via plugin | Hosted platform | Their server | Ignore: not legally open, needs registration |
| [QuantHarness](https://github.com/Y-Research-SBU/QuantHarness) (was QuantAgent) | MIT | 2.9k | 2026-08 | Yes | On demand | None | Ignore: chart-based fast trading |
| [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) | MIT | 38.3k | 2026-11-15 | Not verified | Yes | Audit log | Ignore as dependency: 3,653 commits in 6 months, China-market focus |
| [QuantDinger](https://github.com/OpenByteInc/QuantDinger) | Apache-2.0 | 13.8k | 2026-11-15 | Not checked | Yes | Own stack | Ignore: a full trading platform |
| [TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN) | **Part Apache-2.0, part proprietary** | 33.0k | 2026-09 | Inherited | Inherited | Inherited | Ignore: partly closed |
| [AgenticTrading](https://github.com/Open-Finance-Lab/AgenticTrading) | OpenMDW-1.0 (not OSI-approved) | 0.9k | 2026-11-05 | Not verified | Nightly leaderboard | Database | Reference for a forward leaderboard |
| [StockAgent](https://github.com/MingyuJ666/Stockagent), [nof0](https://github.com/wquguru/nof0), [crewAI-examples](https://github.com/crewAIInc/crewAI-examples) | No licence / archived | - | - | - | - | - | Ignore |

### TradingAgents: the role model for the team, not for the plumbing
A team modelled on a trading firm: four analysts in parallel, a bull and a bear researcher who debate for a fixed number of
rounds, a judge, a trader, a risk debate and a portfolio manager ([paper](https://arxiv.org/abs/2412.20138)). Maintained
software with tests and monthly releases.

Why not use it as a library:
- **Its "append-only" memory log is rewritten in place** when an outcome is added, and old entries are pruned
  ([memory/log.py](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/memory/log.py), `update_with_outcome`
  uses `os.replace`). **[checked]** That breaks our rule that logged decisions are never edited.
- It runs one company through one chain from analysts to decision. Our plan is one shared analyst layer feeding several fund
  setups, which means cutting that chain apart.
- No prompt caching, batch processing, token-cost tracking or budget cap was found (code search for `cache_control` returns 0
  results **[checked]**). These are exactly the features that keep our monthly cost down.
- It is built on LangGraph/LangChain, a large dependency tree that sits between us and the Claude API.
- Its data comes partly from Yahoo (unofficial), Alpha Vantage (closed, 25 calls a day), StockTwits and Reddit.

What to borrow: the role split, the capped bull/bear debate with a judge, a cheap and an expensive model tier, "settle the
decision later and write a short reflection" (as a new record), and its rule that financial data is used "as filed".

### ai-hedge-fund v2: the role model for the bookkeeping
In 2026 this changed from a demo into a small, tested engine. The data layer is [Financial Datasets](https://financialdatasets.ai),
a **closed, paid** service (7 code references **[checked]**), which rules it out as a library for us.

What to borrow, almost one-to-one:
- **The ledger**: one file per trading session, each carrying the hash of the previous one. The fund's state is never stored
  separately but rebuilt by replaying the chain, so an edited, missing or reordered record is detected. A kill-switch file
  stops all trading. Redone records are moved aside, never deleted. **[checked]**
- **A stored copy of the exact prompt and response of every model call**
  ([llm/cache.py](https://github.com/virattt/ai-hedge-fund/blob/main/hedge_fund/llm/cache.py)).
- **The trading-cost model** with a "no-trade band" that suppresses tiny adjustments
  ([brokers/costs.py](https://github.com/virattt/ai-hedge-fund/blob/main/hedge_fund/brokers/costs.py)). Its defaults suit large
  stocks; small biotechs need wider spreads.
- **A runner that never back-fills prices it did not see** at the time.

### FinRobot: one principle
An equity-research report generator. The principle worth copying: "numbers are code-calculated, narratives are LLM-assisted,
every output is provenance-tracked" ([README](https://github.com/AI4Finance-Foundation/FinRobot#readme)).

## 5. Financial data platforms and toolkits

| Project | Licence | Verdict |
|---|---|---|
| [OpenBB](https://github.com/OpenBB-finance/OpenBB) | Apache-2.0 since v5 (Sept 2026); was AGPL, before that MIT ([licence FAQ](https://docs.openbb.co/odp/python/faqs/license)) | Skip. It is a wrapper around ~30 data providers, most of them closed or needing keys. We need one or two. Its stewardship moved to a new organisation in Sept 2026 (details **[unverified]**) |
| [Qlib](https://github.com/microsoft/qlib) (Microsoft) | MIT | Skip: machine-learning factor research, not agents |
| [FinRL](https://github.com/AI4Finance-Foundation/FinRL) | MIT | Skip: reinforcement learning |
| [yfinance](https://github.com/ranaroussi/yfinance) | Code Apache-2.0; **data is Yahoo's, personal use only** | Cross-check and prototyping only; never republish its data |
| [pandas-datareader](https://github.com/pydata/pandas-datareader) | BSD-3 | Handy for the event study (Fama-French factors) |
| [ArcticDB](https://github.com/man-group/ArcticDB) | **BSL 1.1, not open source** | Skip. The idea is right (never overwrite, store when you fetched it); a plain SQLite or DuckDB table does the same |

**Price data has no clean free answer.** See [DATA-SOURCES.md](DATA-SOURCES.md) section 6. In short: every free price source is
a closed service with personal-use terms, and none includes delisted companies for free. For a forward-running fund that needs
about 200 closing prices a day this is workable; for the historical event study it means stating the survivorship bias openly.

## 6. Paper trading, portfolio accounting and backtesting engines

| Project | Licence | State | Why not |
|---|---|---|---|
| [LEAN](https://github.com/QuantConnect/Lean) (QuantConnect) | Apache-2.0 | Active | Needs .NET and Docker; good corporate-action handling only with QuantConnect's own paid data |
| [NautilusTrader](https://github.com/nautechsystems/nautilus_trader) | LGPL-3.0 | Active | Built for high-speed multi-exchange trading; overkill for one decision a day |
| [zipline-reloaded](https://github.com/stefan-jansen/zipline-reloaded) | Apache-2.0 | Active | Closest fit: models splits, mergers, delistings. But we must supply that data ourselves, which is the hard part anyway |
| [vectorbt](https://github.com/polakowo/vectorbt) | **Apache-2.0 + Commons Clause, not open source**; PRO version closed | Active | Not needed |
| [PyBroker](https://github.com/edtechre/pybroker) | **Apache-2.0 + Commons Clause, not open source** | Active | Not needed |
| [backtrader](https://github.com/mementum/backtrader) | GPL-3.0 | **Dead since 2023** | Do not adopt |
| [backtesting.py](https://github.com/kernc/backtesting.py) | AGPL-3.0 | Active | One stock at a time |
| [Ghostfolio](https://github.com/ghostfolio/ghostfolio), [Portfolio Performance](https://github.com/portfolio-performance/portfolio), [beancount](https://github.com/beancount/beancount) | AGPL / EPL / GPL | Active | Built for a person tracking real holdings, not for several automated parallel funds. Beancount's model (dated, never-edited entries) is good design inspiration |

**Recommendation: build a small ledger of our own**, a few hundred lines with tests:
- an append-only table of trades (filled at the next close, plus or minus the cost model);
- a table of corporate actions (reverse split, delisting, cash takeover, share-swap takeover, ticker change), each with a source link;
- raw closing prices with the time we fetched them;
- daily portfolio value, one fund ID per parallel setup;
- **everything keyed on the SEC company number (CIK), never on the ticker**, because tickers change and get reused.

Reuse for the statistics: [empyrical-reloaded](https://github.com/stefan-jansen/empyrical-reloaded) and
[QuantStats](https://github.com/ranaroussi/quantstats) (both Apache-2.0 **[checked]**), fed with our daily values. For the
historical event study: statsmodels and pandas; the dedicated `eventstudy` package has been stale since 2021.

## 7. Biotech-specific tools

### Trial data
| Item | Open? | Verdict |
|---|---|---|
| ClinicalTrials.gov API v2 | Official, no key **[checked: works 2026-11-15]** | Call it directly; the Python wrapper [pytrials](https://github.com/jvfe/pytrials) has had no release since 2024 |
| [AACT](https://aact.ctti-clinicaltrials.org/) | Free copy of the registry as a database; **account required**; licence terms not found | Useful for the historical study; owner decision (sign-up) |
| [cthist](https://cran.r-project.org/package=cthist) (R) | Open | Reconstructs old versions of trial records through an undocumented route that refused scripts today. Historical study only, if at all |

### Trial-outcome prediction models and datasets
| Item | Licence | Problem for us |
|---|---|---|
| [TOP / HINT](https://github.com/futianfan/clinical-trial-outcome-prediction) | Non-commercial usage agreement, not open source | Labels from about 2020-2022; the models already know these outcomes |
| [CTO](https://github.com/sunlabuiuc/CTO) | MIT | **Its success labels are partly derived from share-price moves after the trial**, so using them in a trading project is circular |
| TrialBench, PyTrial, SPOT | Unclear / BSD | Stale |
| [CT Open](https://ct-open.net/) | Open submissions; data licence **[unverified]** | The one to watch. It only scores trials whose results were not yet public. Could be an optional side test for our clinical analyst |

**For a base rate of trial success, use published tables, not a model.** Wong, Siah & Lo (2019), success rates per phase and
disease area from 406,000 trial records, is CC BY 4.0 and free to use with attribution
([MIT record](https://dspace.mit.edu/handle/1721.1/128480)). Human-genetics support for the drug target roughly doubles the odds
(sources in [DATA-SOURCES.md](DATA-SOURCES.md) section 9).

### Catalyst calendars
No dependable open calendar of FDA decision dates or readouts exists. The well-known ones (BiopharmCatalyst, RTTNews,
FDATracker) are **closed** sites whose terms restrict reuse. We build our own: recipe in [DATA-SOURCES.md](DATA-SOURCES.md) section 4.

### SEC filings
| Project | Licence | Verdict |
|---|---|---|
| [edgartools](https://github.com/dgunning/edgartools) | MIT **[checked]**, v6.2.0 released 2026-11-15 **[checked]** | **Reuse.** Insider trades, fund holdings, financial data, filing items. Respects SEC's rate limit and requires a contact identity |
| [sec-edgar-downloader](https://github.com/jadchaar/sec-edgar-downloader) | MIT | Bulk download only |
| sec-api.io | **Closed, paid** | Skip |

### Literature
[Biopython](https://github.com/biopython/biopython) (PubMed access) and [pyalex](https://github.com/J535D165/pyalex) (OpenAlex)
are maintained and open. Europe PMC and bioRxiv are simple enough to call directly. pymed is archived.

### Linking the data ("the glue")
No open dataset maps trial sponsors to stock tickers. Building blocks, all open:

| Source | Links | Licence |
|---|---|---|
| SEC `company_tickers.json` and submissions files | ticker ↔ company number ↔ former names ↔ industry code | US government |
| [OpenFIGI](https://www.openfigi.com/docs/terms-of-service) | ticker ↔ exchange ↔ share class | Identifiers are public domain; the service is run by Bloomberg |
| [GLEIF](https://www.gleif.org/en/lei-data/access-and-use-lei-data) | company ↔ parent company | Free, no registration |
| Wikidata | company ↔ ticker ↔ drugs ↔ trial numbers | CC0; patchy for small companies |
| [ChEMBL](https://www.ebi.ac.uk/chembl/), [Open Targets](https://platform-docs.opentargets.org/licence), FDA GSRS | drug ↔ code names ↔ mechanism ↔ target ↔ trials | CC BY-SA / CC0 / US government |

Proposed recipe: define the universe from SEC industry codes plus listing; generate name variants per company; match them
loosely against trial sponsor names; **a person confirms the roughly 200 matches once**; store the result as a dated table.
Drug code names are extracted from annual reports by an agent and linked through trial records and ChEMBL.

### Tool servers for Claude (MCP)
[cyanheads](https://github.com/cyanheads) publishes active Apache-2.0 servers for ClinicalTrials.gov, PubMed and openFDA;
edgartools ships its own. They are handy for interactive research. **For logged decisions, our own code should fetch the data,
store a snapshot and hand that snapshot to the agent.** An agent that browses live cannot be audited afterwards for what it saw.

### Activity and maturity of the tools named in sections 5 to 7
GitHub figures on 2026-11-15, from the research agent ([notes/B-tools.md](notes/B-tools.md) has the full tables).
"6-month commits" counts the default branch since mid-May 2026; 100+ means the count was capped.

| Project | Stars | Last release | 6-month commits | Maturity |
|---|---|---|---|---|
| OpenBB | 75.4k | v5, 2026-09 | 42 | Maintained; stewardship just changed |
| Qlib | 50.3k | v0.9.8, 2026-10 | 5 | Slowing |
| FinRL | 17.1k | v0.3.8, 2026-03 | 46 | Academic |
| yfinance | 25.9k | 1.8.0, 2026-11 | 100+ | Very active; breaks when Yahoo changes |
| pandas-datareader | 3.3k | v0.11.1, 2026-06 | 41 | Revived in 2026 |
| ArcticDB | 2.6k | v6.28.3, 2026-11 | 100+ | Mature, company-backed |
| LEAN | 22.5k | ships via Docker | 100+ | Mature, heavy |
| NautilusTrader | 31.6k | v1.231.0, 2026-08 | 100+ | Mature, heavy |
| zipline-reloaded | 2.0k | 3.2.1, 2026-10 | 100+ | Maintained |
| vectorbt | 9.9k | v1.2.1, 2026-11 | 100+ | Maintained |
| PyBroker | 3.7k | v2.0.2, 2026-10 | 100+ | Maintained |
| backtrader | 23.7k | none | 0 (last commit 2023-04) | Dead |
| backtesting.py | 9.2k | 0.6.6, 2026-07 | 27 | Maintained |
| QuantStats | 7.9k | v0.0.86, 2026-09 | 10 | Maintained, slow |
| empyrical-reloaded | 0.1k | 0.7.2, 2026-11 | 100+ | Maintained, small community |
| edgartools | 2.9k | v6.2.0, 2026-11-15 | 100+ | Very active, one main author |
| sec-edgar-downloader | 0.7k | 5.1.0, 2026-02 | 0 | Stable, quiet |
| Biopython | 5.3k | 1.88, 2026-08 | 93 | Mature |
| pyalex | 0.4k | v0.21, 2026-02 | 0 | Quiet |
| pytrials | 61 | v1.0.0, 2024-05 | 0 | Stale |
| TOP / HINT | 173 | none | 0 (last commit 2025-06) | Research artefact |
| CTO | 18 | none | 0 (last commit 2026-02) | Research artefact |
| cyanheads ClinicalTrials.gov / PubMed servers | 101 / 168 | v2.11 / v2.12, 2026-11 | 100+ | Very active, young |

## 8. Licence traps

| Looks open | Actually |
|---|---|
| vectorbt, PyBroker | Apache-2.0 **plus Commons Clause**: source-available, not open source |
| ArcticDB | Business Source License 1.1 |
| AI-Trader, StockAgent, nof0 | README says MIT or nothing; **no licence file**, so no rights are granted |
| TradingAgents-CN | Core Apache-2.0, application and front end proprietary |
| LiveTradeBench code | PolyForm Noncommercial |
| TOP / HINT data | Non-commercial usage agreement |
| yfinance | Open code, closed data with personal-use terms |

## 9. Build versus reuse

| Component | Reuse | Build | Why |
|---|---|---|---|
| Agent orchestration | Designs from TradingAgents (roles, capped debate, judge) | A few hundred lines on the plain Anthropic SDK | Frameworks weld analysts to decisions and hide caching, batch and token counts |
| Decision log | Design from ai-hedge-fund v2 (hash chain, replay, kill switch) | Own implementation | Their code is tied to their data service |
| Record of each model call | Design from ai-hedge-fund v2 | Own table: prompt, response, tokens, cost | Needed for audit and for the cost cap |
| Token budget and hard stop | Nothing found | Own | No framework has it |
| Trading costs | Cost model design from ai-hedge-fund v2 | Re-tuned for small-cap spreads | Defaults are for large stocks |
| Paper ledger and accounting | Beancount's design ideas | Own SQLite or DuckDB tables | Engines are heavy and still leave corporate actions to us |
| Corporate actions | edgartools to read the filings | Own event table and rules | No open feed exists |
| Performance statistics | **empyrical-reloaded, QuantStats** | - | Light and standard |
| Event study (history) | statsmodels, pandas | Short script | Dedicated packages are stale |
| SEC filings | **edgartools** | - | Best maintained |
| Trial data | ClinicalTrials.gov API directly | Small client plus daily snapshots and comparison | The API keeps no history |
| Trial base rates | Wong-Siah-Lo tables; genetics evidence | Lookup table | Open and citable; models are stale or contaminated |
| Catalyst calendar | - | Agent extracts dates from filings; every entry dated and versioned | No open calendar exists |
| Literature | **Biopython, pyalex**; Europe PMC and bioRxiv directly | - | Mature and open |
| Linking companies, drugs and trials | SEC files, OpenFIGI, Wikidata, GLEIF, ChEMBL, Open Targets | Alias tables plus a one-time human check | The core data asset of the project |
| Storage | SQLite or DuckDB | Schema | Enough for 200 companies |
| Prices | One closed free service (see data report) | Fetcher and our own archive | No open source exists |

## 10. Recommended stack (proposal)

**Open source, reuse as libraries:** Python with uv; the Anthropic SDK; edgartools (MIT); empyrical-reloaded and QuantStats
(Apache-2.0); statsmodels and pandas; Biopython; SQLite or DuckDB; Docker Compose and systemd timers as already used on the server.

**Open source, borrow the design only:** TradingAgents (team structure), ai-hedge-fund v2 (ledger, call records, cost model),
FinRobot (numbers in code), Beancount (never-edited dated entries).

**Build ourselves:** the orchestrator with shared analyst layer and several decision setups; the tamper-evident decision log;
the token ledger with a hard monthly stop; the paper ledger with corporate actions; daily snapshot-and-compare for sources that
overwrite their history; the catalyst calendar; the company-drug-trial linking tables.

**Closed or proprietary, stated plainly:**
- **Claude API** (Anthropic): closed and paid. It is the engine of the project.
- **A price source**: every option is a closed service with personal-use terms.
- **Yahoo via yfinance**: closed data, personal use only; cross-check at most.
- **OpenFIGI**: the identifiers are public domain, but the lookup service is run by Bloomberg.
- Everything else in the proposed stack is open source or official open data.

**Deliberately not used:** LangChain/LangGraph, OpenBB, any backtesting engine, paid transcript or catalyst-calendar services,
social-media APIs.

## 11. Limits of this report
- Based on reading repositories and papers, not on running anything.
- Most trading-agent evidence is preprints; only FINSABER, DeepFund, CT Open and the forecasting papers are peer-reviewed.
- Not verified: Alpha Arena numbers (press only); Claude support in FinRobot v2, Vibe-Trading and AgenticTrading; the OpenBB
  stewardship change; licences of CT Open data, AACT and TrialBench.
- "No prompt caching in TradingAgents" rests on a code search; it could in theory be enabled indirectly by a dependency.
- The six-month sample-size estimate is a back-of-envelope figure and should be redone properly in the spec.
