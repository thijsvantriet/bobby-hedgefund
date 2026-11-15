# B. Tools and libraries: what to reuse, what to build (research 2026-11-15)

Checked 2026-11-15. GitHub numbers come from `gh api repos/...` (stars, latest release, last commit, and commits on the default branch since 2026-05-15, capped at 100, so "100" means 100 or more). PyPI metadata comes from `pypi.org/pypi/<pkg>/json`. Licences were read from each repo's LICENSE file through `gh api repos/X/license`. Anything marked **unverified** comes from memory or a secondary source and was not checked against a primary source today.

**Legend:** OSS = open source (OSI licence). "Source-available" = you can read the code, but the licence restricts use (Commons Clause, BSL), so it is not OSI open source. CLOSED = proprietary service or software.

---

## Headline answers

1. **Free, legally clean end-of-day US prices with splits, dividends and delisted tickers: no free source covers all of it.** Yahoo/yfinance is personal-use only and has no delisted tickers. Stooq is free, but its terms were not verified. The free tiers of Tiingo, Alpha Vantage, Massive (formerly Polygon), EODHD and Finnhub are all CLOSED, limited, and mostly "personal use". For a forward-only paper fund this matters less than it seems:
   - We only need **today's close for ~200 tickers**.
   - We can record splits and delistings ourselves as they happen, from SEC 8-Ks and exchange notices, plus the provider's split field.
   - Delisted-ticker history only matters for the historical event study. There, the gap creates survivorship bias, which we should state openly.
   - Pragmatic choice: one closed free tier (Tiingo, or Massive Basic), with yfinance as a cross-check. Store the raw closes ourselves.
2. **Backtesting/paper engines: none is worth its weight** for a daily, long-only, ~30-position paper book. None of them handles reverse splits, delistings, cash mergers and ticker changes in small biotechs from open data. Zipline-reloaded comes closest: it has a splits/mergers/dividends adjustment model, but you have to feed it the data. **Build a small own ledger**: an append-only trades table, a corporate-actions table, and a daily mark-to-market. Use **empyrical-reloaded / QuantStats** for the performance statistics.
3. **Biotech glue is the hard part, and no open ticker↔sponsor mapping of any quality exists.** We build it ourselves from these pieces:
   - SEC `company_tickers.json` (ticker↔CIK)
   - ClinicalTrials.gov sponsor strings
   - Wikidata (CC0)
   - OpenFIGI (public domain)
   - ChEMBL / Open Targets (drug↔trial)
   - a hand-curated alias table for ~200 companies
4. **Best-maintained building blocks:**
   - **edgartools**: MIT, very active, enforces SEC rate limits and requires an identity
   - **cyanheads MCP servers** for ClinicalTrials.gov, PubMed and openFDA: Apache-2.0, very active
   - **Biopython Entrez** and **pyalex** for literature
   - **AACT** for bulk trial SQL
5. **Trial-outcome models/datasets** (TOP/HINT, CTO, TrialBench, PyTrial) are mostly stale, and some are non-commercial. CTO's labels partly come *from stock-price moves*, so they are circular and leak information for our purpose. **CT Open**, a live, contamination-controlled benchmark started in 2026, is the interesting one to watch. For a base-rate input, use **Wong-Siah-Lo 2019**, which is CC BY 4.0.

---

## B1. Financial data platforms and research toolkits

| Project | Licence (open?) | Stars | Last release | Last commit | 6-mo commits | Install weight | Data it depends on | Verdict |
|---|---|---|---|---|---|---|---|---|
| OpenBB (ODP v5) | Apache-2.0 (OSS) since v5; v4 and earlier AGPL-3.0 | 75.4k | ODP tag 2026-09-30 (PyPI 5.0.0, 2026-09-29) | 2026-11-15 | 42 | Pure-Python wheel, Py ≥3.10, uv OK; many optional extras | Wrapper around providers (yfinance, FMP, Polygon, Tiingo, SEC, …); most are closed/keyed | Optional facade, not needed |
| Microsoft Qlib | MIT (OSS) | 50.3k | v0.9.8 2026-10-08 | 2026-10-08 | 5 | Compiled wheels, heavy ML stack | Own data format; community Yahoo dumps | Not for us |
| FinRL | MIT (OSS) | 17.1k | v0.3.8 2026-03-20 | 2026-10-25 | 46 | Heavy (RL libs) | yfinance, others | Not for us |
| FinRL-Meta | MIT (OSS) | 2.0k | v0.3.6 2022-06-26 | 2026-09-28 | 6 | Heavy | Many processors | Not for us |
| yfinance | Apache-2.0 code (OSS); data is Yahoo's (CLOSED, personal use) | 25.9k | 1.8.0 2026-11-03 | 2026-11-07 | 100+ | Pure Python, uv OK | Unofficial Yahoo endpoints | Cross-check / prototyping only |
| pandas-datareader | BSD-3 (OSS) | 3.3k | v0.11.1 2026-06-24 | 2026-07-21 | 41 | Pure Python, Py ≥3.11 | Stooq, FRED, Tiingo, AV, … | Handy Stooq/FRED reader |
| akshare | MIT (OSS) | 23.3k | v1.20.65 2026-11-15 | 2026-11-15 | 100+ | Pure Python | Scrapes mostly Chinese sites; some US via Sina/EastMoney | Not for us |
| FinanceToolkit | MIT (OSS) | 5.5k | v2.3.4 2026-11-14 | 2026-11-15 | 100+ | Pure Python, Py 3.11–3.15 | FMP (CLOSED, keyed) + Yahoo fallback | Ratio formulas as reference at most |
| ArcticDB | **BSL 1.1** (source-available, NOT OSS; free unless offered as a "Database Service") | 2.6k | v6.28.3 2026-11-02 | 2026-11-13 | 100+ | C++ manylinux wheel | n/a (storage) | Overkill; SQLite/DuckDB plus append-only tables suffice |

**Closed data services (free tiers, checked 2026-11-15)**

| Service | Free tier (verified where linked) | Delisted? | Terms |
|---|---|---|---|
| Yahoo Finance (via yfinance) | No key; unofficial, rate-limited | No | yfinance README: "intended for personal use only" ([README](https://github.com/ranaroussi/yfinance)) |
| Stooq | Free CSV downloads, no key | unverified | Terms not found on primary source: **unverified** |
| Tiingo | 1,000 req/day, 50/h (secondary source); free accounts for personal use, commercial use needs a paid plan ([docs](https://api.tiingo.com/documentation)) | unverified | CLOSED |
| Alpha Vantage | 25 req/day ([support](https://www.alphavantage.co/support/)); unlimited for "verified open-source or educational projects" | unverified | CLOSED |
| Massive (formerly Polygon.io) | Free "Basic" plan exists; all individual plans are "individual use only" ([pricing](https://massive.com/pricing)). 5 calls/min and 2 years of history: **unverified** (from memory) | Paid plans list delisted tickers; on Basic: unverified | CLOSED |
| EODHD | 20 calls/day, 1 year of EOD ([pricing](https://eodhd.com/pricing)); cheapest EOD plan $19.99/mo | Paid "delisted" API | CLOSED |
| Finnhub | Free tier exists; whether daily candles are free: **unverified** | unverified | CLOSED |

**Notes**

- **OpenBB.** A Python "Open Data Platform": one API, CLI and MCP server across dozens of data providers.
  - **Licence history:** MIT → AGPL-3.0 (May 2024, [blog](https://openbb.co/blog/license-change-openbb-platform-goes-agpl/)) → Apache-2.0 for v5 ([licence FAQ, updated 2026-09-29](https://docs.openbb.co/odp/python/faqs/license)). The repo LICENSE now says "All files in this repository are licensed under the Apache License, Version 2.0".
  - **Stewardship change (important):** `github.com/OpenBB-finance/OpenBB` now redirects to `github.com/openbq-org/OpenBB`, an org created 2026-09-11. A search result reports a founder post (Aug/Oct 2026) saying OpenBB open-sourced its whole suite, created **OpenBQ**, a non-profit steward led by BrightQuery's CEO, and handed the Workspace code to FINOS. I did not read that post myself, so this is **partly unverified**. The paid OpenBB Workspace is therefore no longer clearly a closed product. Either way, the data itself comes from the providers, and most of those are closed or keyed.
  - **Reuse:** at most a design pattern (a provider-adapter layer). We need one price source, not 30. Verdict: skip.
- **Qlib.** Microsoft's quant ML research platform: data layer, alpha models, backtest. Strong for factor ML; irrelevant for LLM agents with ~200 tickers. 5 commits in 6 months means slowing. Skip.
- **FinRL / FinRL-Meta.** Deep-RL trading frameworks. Academic, heavy, and FinRL-Meta has had no release since 2022. Skip.
- **yfinance.** Scrapes Yahoo's unofficial endpoints and returns OHLCV, splits, dividends and some fundamentals. Very active. The code is Apache-2.0, but **the data rights are Yahoo's**: the README points to Yahoo's terms and says the API is "intended for personal use only" ([repo](https://github.com/ranaroussi/yfinance)). It breaks occasionally when Yahoo changes its endpoints, and it has no delisted tickers. Acceptable for a private hobby paper fund as a cross-check. Not for redistribution.
- **pandas-datareader.** Revived in 2026 (v0.11.1). Readers for FRED, Stooq, Fama-French and others. Useful for Fama-French factors and FRED in the event study.
- **akshare.** Mostly China-market scrapers. Skip.
- **FinanceToolkit.** Ratio and metric calculations on top of FinancialModelingPrep (CLOSED, keyed). Skip; for biotech we read cash and runway from XBRL via edgartools instead.
- **ArcticDB.** Man Group's versioned dataframe database with time travel, the textbook choice for point-in-time storage. **BSL 1.1 is not open source.** Overkill for ~200 tickers × daily data. The point-in-time *pattern* is what matters: never overwrite, store `as_of` and `retrieved_at`. A plain SQLite/DuckDB table gives us that.

---

## B2. Paper-trading, portfolio accounting, backtesting engines

| Project | Licence (open?) | Stars | Last release | Last commit | 6-mo | Install weight | Corporate actions? | Verdict |
|---|---|---|---|---|---|---|---|---|
| QuantConnect LEAN | Apache-2.0 (OSS) | 22.5k | (GitHub "latest" is an old 2017 tag; ships via Docker/CLI) | 2026-11-15 | 100+ | **.NET/C#**, Docker images, large | Yes, with QuantConnect's own (paid) data | Too heavy |
| NautilusTrader | LGPL-3.0 (OSS) | 31.6k | v1.231.0 2026-08-02 | 2026-11-14 | 100+ | Rust core, binary wheels, **Py 3.12–3.14 only** | Event-driven; you supply the data | Too heavy for daily runs |
| vectorbt (open) | **Apache-2.0 + Commons Clause** (source-available, NOT OSS) | 9.9k | v1.2.1 2026-11-11 | 2026-11-11 | 100+ | Pure-Python wheel (numba) | No | Not needed |
| vectorbt PRO | CLOSED, paid | – | – | – | – | – | – | Skip |
| backtrader | GPL-3.0 (OSS) | 23.7k | none | **2023-04-19** | 0 | Pure Python | Manual | Dead |
| zipline-reloaded | Apache-2.0 (OSS) | 2.0k | 3.2.1 2026-10-25 | 2026-11-02 | 100+ | Compiled wheels, Py 3.11–3.14, pandas <3 | **Yes**: splits, mergers, dividends adjustment tables, asset lifetimes (data must be supplied as a "bundle") | Closest fit, still overkill |
| backtesting.py | **AGPL-3.0** (OSS) | 9.2k | PyPI 0.6.6 2026-07-22 | 2026-08-05 | 27 | Pure Python | No (single asset) | Not suitable (single instrument) |
| bt | MIT (OSS) | 3.0k | v1.4.1 2026-10-10 | 2026-11-13 | 100+ | Compiled wheels | No | Possibly for strategy-tree prototyping; not needed |
| PyBroker | **Apache-2.0 + Commons Clause** (source-available) | 3.7k | v2.0.2 2026-10-20 | 2026-10-20 | 100+ | sdist only | No | Skip |
| QuantStats | Apache-2.0 (OSS) | 7.9k | v0.0.86 2026-09-27 | 2026-11-02 | 10 | Pure Python | n/a | **Reuse** (tear sheets) |
| pyfolio-reloaded | Apache-2.0 (OSS) | 0.6k | 0.10.2 2026-11-02 | 2026-11-02 | 29 | Pure Python | n/a | Optional |
| empyrical-reloaded | Apache-2.0 (OSS) | 0.1k | 0.7.2 2026-11-05 | 2026-11-08 | 100+ | Pure Python, Py ≥3.11 | n/a | **Reuse** (Sharpe, drawdown, alpha/beta) |
| alphalens-reloaded | Apache-2.0 (OSS) | 0.7k | 0.5.1 2026-10-26 | 2026-10-26 | 21 | Pure Python | n/a | Optional (factor or signal decay analysis) |
| beancount v3 | GPL-2.0 (OSS) | 6.2k | PyPI 3.2.3 2026-05-05 | 2026-08-23 | 6 | Compiled wheel | Manual entries; lot tracking | Design inspiration |
| ledger | BSD-3 (OSS) | 6.1k | v3.4.1 2025-10-26 | 2026-11-09 | 100+ | C++ binary | Manual | No |
| Portfolio Performance | EPL-1.0 (OSS) | 4.2k | 0.90.0 2026-11-01 | 2026-11-15 | 100+ | Java desktop app | Manual / quote feeds | Nice manual viewer, not automatable |
| Ghostfolio | AGPL-3.0 (OSS) | 9.7k | 3.100.0 2026-11-15 | 2026-11-15 | 100+ | Docker (Node + Postgres + Redis) | Via Yahoo / closed providers | Too heavy for N parallel funds |
| rotki | AGPL-3.0 (OSS) | 4.1k | v1.44.3 2026-11-11 | 2026-11-15 | 100+ | Electron/Python app | Crypto-focused | No |
| eventstudy (PyPI) | no licence stated on PyPI | – | 0.1a12 **2021** | – | – | Pure Python | n/a | Stale; use statsmodels |

**Notes**

- **LEAN.** QuantConnect's C# engine; Python strategies run via pythonnet. It handles splits, dividends, delistings and symbol changes very well, but only with QuantConnect's own data formats and (paid) data. Needs Docker and .NET. Too heavy and too coupled for our use.
- **NautilusTrader.** A high-performance, event-driven engine with a Rust core, built for live and backtest parity in HFT and multi-venue trading. LGPL is fine for us. It is overkill for one decision per day, and it pins Python 3.12–3.14.
- **vectorbt.** Fast vectorised research. The open version is Apache-2.0 *with Commons Clause*, so it is not OSI open source; PRO is closed and paid. No corporate-action handling.
- **backtrader.** No commits since 2023. Do not adopt.
- **zipline-reloaded.** Stefan Jansen's maintained fork of Quantopian's Zipline, very active in 2026. It has the most complete corporate-action model of the Python engines: adjustment tables for splits, mergers and dividends, plus asset start/end dates for delistings. **It does not supply the data.** You write a "bundle" yourself, so the hard part (where corporate actions come from) stays ours. Its daily-bar, pipeline-oriented design also fits LLM decisions poorly.
- **backtesting.py.** AGPL, single-instrument. Not a portfolio engine.
- **bt.** A strategy-tree (algos) framework on top of ffn. A fine library, but it adds nothing over our own ledger.
- **QuantStats / empyrical-reloaded / pyfolio-reloaded.** Performance statistics and HTML tear sheets from a daily returns series. Feed them our NAV series. Light pure-Python wheels.
- **Accounting tools.** Beancount's model (immutable dated transactions, cost-basis lots, balance assertions, price directives) is the right *design pattern* for an append-only paper ledger. Running Beancount itself across several parallel funds adds a text DSL with no gain. Portfolio Performance is a nice desktop viewer for a human, but it is not automatable. Ghostfolio is a full web stack in Docker.

**Where would open corporate-action data come from?** No free, open, clean feed exists (to my knowledge, **unverified** that none does). Practical sources:
- **SEC EDGAR** 8-K filings: Item 3.01 (delisting notice), Item 5.03 (charter amendment, often a reverse split), Item 2.01 (completed merger), Form 25 (delisting), plus S-4/DEFM14A filings for mergers. All parseable with edgartools.
- **Nasdaq Trader** daily symbol-directory files and corporate-action lists (`nasdaqtrader.com`; terms **unverified**).
- **The price provider's split/dividend fields** (yfinance `actions`, Tiingo `splitFactor`/`divCash`).
- Ticker changes: SEC `company_tickers.json` diffs. A CIK stays the same when the ticker changes, so **key everything on CIK, never on ticker**.

**Recommendation (build).** Use SQLite or DuckDB, one database per run, with a `fund_id` column for the parallel setups. Tables:
- `trades` (append-only; fill price = next close ± a cost model)
- `corporate_actions` (type, ratio, cash, new_cik/ticker, effective date, source URL)
- `prices_eod` (raw close, retrieved_at)
- `nav_daily`

Positions are derived as views. Apply a reverse split by adjusting the share count of open lots. A delisting turns into a forced sale at the last trade price, or at 0. A cash merger becomes a sale at the deal price. A stock merger becomes a swap into the acquirer. This is roughly 300–500 lines of Python plus tests, and it is fully transparent.

**Event-study tooling.** `statsmodels` (OLS market model) plus pandas covers the standard MacKinlay (1997) approach: estimation window, abnormal returns, CAR, t-tests. The `eventstudy` PyPI package has been stale since 2021. alphalens-reloaded fits signal-decay views. Benchmark: XBI/IBB closes, plus Fama-French factors via pandas-datareader.

---

## B3. Biotech-specific open tools

### B3a–b. Trial data, NLP, outcome prediction

| Project | Licence (open?) | Stars | Last release | Last commit | 6-mo | Notes | Verdict |
|---|---|---|---|---|---|---|---|
| ClinicalTrials.gov API v2 | US government data, public; terms page not loaded (**unverified**) | – | – | – | – | REST/JSON, no key; rate limit ~50 req/min per IP (**unverified**) | **Primary source**; call it directly with `httpx` |
| pytrials (jvfe) | BSD-3 (OSS) | 61 | v1.0.0 2024-05-01 | 2024-05-01 | 0 | Thin v2 wrapper | Stale; write our own 50-line client |
| AACT (CTTI) | Data derived from CT.gov; licence not stated on homepage (**unverified**) | – | – | – | – | Daily-refreshed PostgreSQL (cloud, free account) plus downloadable snapshots ([site](https://aact.ctti-clinicaltrials.org/)) | **Reuse** for bulk/historical SQL (event-study case library) |
| TrialGPT (NCBI) | US public domain (OSS-compatible) | 184 | v1.0.0 2024-08-08 | 2025-01-24 | 0 | Patient-to-trial matching with LLMs | Pattern only |
| TOP benchmark + HINT | **Non-commercial "Benchmark Usage Agreement"**, no OSS licence | 173 | none | 2025-06-24 | 0 | HINT published in Patterns 2022; phase I/II/III approval prediction | Hobby use OK under non-commercial terms; stale |
| CTO (sunlabuiuc/CTO; old chufangao/CTOD archived 2026-02-06) | MIT (code and HF dataset) | 18 / 31 | none | 2026-02-18 | 0 | Weak-supervision labels for ~hundreds of thousands of trials; data up to ~2024-09 | **Caution**: labels partly come from stock-price moves and news, so they are circular for us |
| TrialBench | Licence not found (**unverified**) | – | – | – | – | 23 datasets / 8 tasks, CT.gov trials registered before 2024-02-16; Sci Data 2025 | Reference only |
| SPOT | Code in PyTrial | – | – | – | – | Meta-learning; claims PR-AUC lifts of 21.5% / 8.9% / 5.5% (phase I/II/III) | Skip |
| PyTrial | BSD-2 (OSS) | 5 | none | 2024-01-08 | 0 | Library of trial-ML models (HINT, SPOT, …) | Stale; skip |
| ML2ClinicalTrials | MIT | 53 | none | 2025-08-06 | 0 | Survey/paper list | Reading list |
| **CT Open** | Platform; licence of question sets **unverified** | – | – | – | – | Live, quarterly, contamination-controlled benchmark of arm-level outcomes (arXiv 2604.16742, Apr 2026) | **Watch / possibly enter**: its design matches our "forward only" rule |

**Notes**

- **ClinicalTrials.gov v2 / AACT.** For ~200 companies, a daily poll of the v2 API filtered by sponsor or NCT list is enough. Use AACT, which is relational and convenient for "all phase-3 completions by sponsor X since 2010", in the historical case library. AACT requires a free account, and its licence terms were not found on the homepage (**check before automating**).
- **TOP/HINT.** The usage agreement restricts it to non-commercial use only ([repo](https://github.com/futianfan/clinical-trial-outcome-prediction)). A private hobby is fine, but it is not open source. Labels date from ~2020–2022.
- **CTO.** Labels combine GPT-3.5 reading PubMed abstracts, phase linkage, news-headline sentiment via SerpAPI, **and stock-price slopes after completion**, fused by a random forest tuned on TOP ([README](https://github.com/sunlabuiuc/CTO)). For a fund that trades on outcomes, the stock-price labelling function makes the labels partly circular. Also, any LLM has probably seen these outcomes, which violates our no-look-ahead rule for scoring.
- **CT Open.** The only design built to prevent training-data contamination: it scores predictions only on trials whose outcomes were not yet public at submission. The paper reports that Claude Opus 4.5 did well on Winter 2025 but dropped on post-cutoff Summer 2025, per a secondary summary ([arXiv](https://arxiv.org/abs/2604.16742)). That supports our project rule of forward-only scoring.
- **Base rates (open).** Wong, Siah & Lo, *Biostatistics* 2019, "Estimation of clinical trial success rates and related parameters": CC BY 4.0 per the [MIT DSpace record](https://dspace.mit.edu/handle/1721.1/128480). It reports phase-transition probabilities by therapeutic area from 406k trial records (2000–2015). Free to cite and embed, with attribution. Project ALPHA's updated quarterly estimates live on the MIT LFE site, terms **unverified**. The BIO/Informa/QLS "Clinical Development Success Rates" reports (2016, 2021) are free PDFs, but their reuse licence is **unverified** (likely all rights reserved). Quote figures with citation; do not redistribute.

### B3c. Catalyst calendars

| Source | Open? | Note |
|---|---|---|
| BiopharmCatalyst, RTTNews FDA calendar, FDATracker, BioPharmCatalyst-like sites | **CLOSED** sites; scraping likely against their ToS (individual terms **unverified**) | Do not scrape |
| GitHub hobby repos (e.g. [palashpawar/biocatalyst](https://github.com/palashpawar/biocatalyst) MIT, 0★, Oct 2026; [Nidhi-bhai/pdufa-calendar](https://github.com/Nidhi-bhai/pdufa-calendar) no licence; [AnasAlzahrani/rct-trader](https://github.com/AnasAlzahrani/rct-trader) MIT, 1★, maps sponsors to tickers) | Tiny, unmaintained, mostly unlicensed | Ideas only; no dependable open dataset found |
| **Build:** PDUFA dates from company 8-Ks and press releases on EDGAR (full-text search), readout windows from CT.gov `primaryCompletionDate` | Open | Recommended: an LLM extracts the dates from filings, with a source URL per event |

No reputable open PDUFA or readout dataset was found on GitHub. A Hugging Face search was not done (**unverified**).

### B3d. SEC / EDGAR

| Project | Licence | Stars | Last release | Last commit | 6-mo | Fair-access handling | Verdict |
|---|---|---|---|---|---|---|---|
| **edgartools** | MIT (OSS) | 2.9k | v6.2.0 2026-11-15 | 2026-11-15 | 100+ | Requires `set_identity()` (contact email); keeps to 10 req/s ([README](https://github.com/dgunning/edgartools)) | **Reuse**: Form 4, 13F, XBRL financials, 8-K items, full-text search; Py ≥3.11, pure wheel; includes an MCP server (`uvx edgartools-mcp`) |
| sec-edgar-downloader | MIT | 723 | 5.1.0 2026-02-02 | 2026-02-02 | 0 | Requires company name + email | Bulk file download only |
| secedgar | Apache-2.0 | 1.4k | v0.6.0 2025-05-09 | 2025-12-09 | 0 | User-agent required (per docs, **unverified**) | Slower maintenance |
| py-edgar (joeyism) | GPL-3.0 | 242 | 5.4.3 2022 | 2024-10 | 0 | – | Stale |
| OpenEDGAR (LexPredict) | MIT | 332 | – | 2019 | 0 | – | Dead |
| Arelle | Apache-2.0 | 259 | 2.47.5 2026-11-12 | 2026-11-13 | 100+ | n/a (XBRL processor) | Not needed: edgartools plus SEC `companyfacts` JSON cover it |
| sec-api.io | **CLOSED, paid** | – | – | – | – | – | Skip |
| sec-edgar-mcp (stefanoamorelli) | AGPL-3.0 | 386 | v1.1.0 2026-08-20 | 2026-10-03 | 24 | Built on edgartools (**unverified**) | Alternative MCP |

SEC rules ([Accessing EDGAR data](https://www.sec.gov/os/accessing-edgar-data)): a maximum of 10 requests/s, and a declared User-Agent with a company name and admin contact email. The SEC "reserves the right to limit request rates". Also free and bulk: `company_tickers.json`, `submissions/CIK##########.json`, `companyfacts` XBRL JSON, and nightly bulk zips. These are US government data with no copyright (general knowledge, **unverified** today).

### B3e. Literature clients

| Project | Licence | Stars | Last release | 6-mo | Verdict |
|---|---|---|---|---|---|
| Biopython (Bio.Entrez) | Biopython License / BSD-3 (OSS) | 5.3k | PyPI 1.88 2026-08-06 | 93 | **Reuse** for PubMed (NCBI: 3 req/s without a key, 10 with one; email/tool parameters required, **unverified** today) |
| metapub | Apache-2.0 | 160 | v0.7.5 2026-09-24 | 14 | Optional (nicer PubMed objects, DOI/PMID linking) |
| pymed | MIT, **archived** | 214 | – | 0 | Dead |
| paperscraper | MIT | 547 | v1.1.0 2026-10-08 | 15 | Optional (bioRxiv/medRxiv/chemRxiv dumps, PubMed); Py <3.14 |
| pyalex (OpenAlex) | MIT | 432 | v0.21 2026-02-23 | 0 | **Reuse** (OpenAlex data is CC0; polite pool takes an email, **unverified**) |
| semanticscholar | MIT | 485 | v0.12.0 2026-03-29 | 4 | Optional |
| Europe PMC REST | Open API, no key (**unverified**) | – | – | – | Call directly with httpx; it has a sponsor/grant search |
| bioRxiv API (api.biorxiv.org) | Open API (**unverified**) | – | – | – | Call directly |

### B3f. Entity linking ("the glue")

| Source | What it links | Licence / terms | Open? |
|---|---|---|---|
| SEC `company_tickers.json` | ticker ↔ CIK ↔ name (current listings only) | US government (**unverified**) | Open |
| SEC submissions JSON | CIK ↔ former names, SIC code (2834/2836 = pharma/bio), exchange, ticker history | US government | Open |
| OpenFIGI | ticker ↔ FIGI ↔ exchange/share class | FIGIs dedicated to the **public domain**, commercial use and redistribution allowed ([ToS](https://www.openfigi.com/docs/terms-of-service)); free API key optional, rate limits not on ToS page | Open data, Bloomberg-run service |
| GLEIF LEI | company ↔ LEI ↔ parent; ISIN↔LEI files | Free, no registration ([GLEIF](https://www.gleif.org/en/lei-data/access-and-use-lei-data)); CC0 per general knowledge (**unverified** today) | Open |
| ROR | research-organisation IDs (universities, some companies) | CC0 (**unverified**) | Open; weak for small companies |
| Wikidata | company ↔ ticker (P249) ↔ CIK (P5531) ↔ LEI ↔ drugs ↔ NCT IDs (P3098) | CC0 (property IDs **unverified**) | Open; coverage of small caps is patchy |
| FDA GSRS / UNII | substance ↔ UNII ↔ code names | US government, public (**unverified**) | Open |
| RxNorm (NLM) | drug names ↔ RxCUI (marketed drugs only) | UMLS licence needed for some sources (**unverified**) | Mostly open |
| ChEMBL | molecule ↔ synonyms/code names ↔ indications (with CT.gov refs) ↔ mechanism | CC BY-SA 3.0 (per [Open Targets licence page](https://platform-docs.opentargets.org/licence)) | Open (share-alike) |
| DrugCentral | approved drugs ↔ targets ↔ labels | CC BY-SA 4.0 (**unverified**) | Open |
| Open Targets Platform | target ↔ disease ↔ drug, clinical evidence via ChEMBL (with NCT refs, **unverified**) | Data CC0, code Apache-2.0 ([licence](https://platform-docs.opentargets.org/licence)) | Open; no company/sponsor field (**unverified**) |
| Sponsor → ticker mapping | **No reputable open dataset found.** CTO's `stock_price` module did a mapping for its own use (code MIT, quality unknown); rct-trader is a 1★ hobby repo | – | Build |

**Practical glue recipe (build).**
1. Universe = SEC submissions with SIC 2834/2836 plus Nasdaq/NYSE listing, filtered on market cap. Key everything on **CIK**.
2. For each company, compute name variants: the SEC name, former names, and Wikidata/GLEIF aliases with legal suffixes stripped. Match them fuzzily against CT.gov `leadSponsor`/`collaborators`, then **have a human confirm** the ~200 matches once. Store the result as a versioned `company_alias` table.
3. Drug assets: an LLM extracts code names (e.g. "ABC-123") from 10-K pipeline tables. Link them via the CT.gov `interventions` names and ChEMBL/GSRS synonyms.
4. Papers via PubMed/OpenAlex searches on drug code names plus NCT IDs. PubMed abstracts carry NCT IDs in their databank fields.

### B3g. MCP servers (agents run on Claude)

| Server | Licence | Stars | Last release | 6-mo | Verdict |
|---|---|---|---|---|---|
| [cyanheads/clinicaltrialsgov-mcp-server](https://github.com/cyanheads/clinicaltrialsgov-mcp-server) | Apache-2.0 | 101 | v2.11.3 2026-11-13 | 100+ | Good candidate (TypeScript/Node) |
| [cyanheads/pubmed-mcp-server](https://github.com/cyanheads/pubmed-mcp-server) | Apache-2.0 | 168 | v2.12.2 2026-11-13 | 100+ | Good candidate |
| [cyanheads/openfda-mcp-server](https://github.com/cyanheads/openfda-mcp-server) | Apache-2.0 | 4 | pushed 2026-11-13 | – | Young |
| edgartools MCP (`edgartools[ai]`) | MIT | (see edgartools) | 6.2.0 | 100+ | **Best EDGAR option** (Python, same lib) |
| [stefanoamorelli/sec-edgar-mcp](https://github.com/stefanoamorelli/sec-edgar-mcp) | AGPL-3.0 | 386 | v1.1.0 2026-08-20 | 24 | Alternative |
| OpenBB MCP server (`openbb-mcp-server`) | Apache-2.0 | – | v5 | – | Only if using OpenBB |
| JackKuo666/ClinicalTrials-MCP-Server | **no licence** | 18 | – | 0 | Avoid |
| Augmented-Nature/OpenFDA-MCP-Server | NOASSERTION | 26 | – | – | Avoid (licence unclear) |

Design caution: for **logged, reproducible decisions**, it is better for our Python code to fetch the data, store a snapshot, and pass the snapshot to the agent, rather than let agents browse through MCP. MCP is handy for interactive research sessions. The cyanheads servers need Node, either in Docker or via `npx`.

---

## Draft build-vs-reuse table

| Component | Reuse | Build ourselves | Why |
|---|---|---|---|
| EOD prices (forward) | One closed free tier (Tiingo or Massive Basic) + yfinance as cross-check; **closed data** | Thin fetcher + raw `prices_eod` table with `retrieved_at` | No open, clean, free US EOD source exists; we only need ~200 closes a day |
| Historical prices (event study) | yfinance / Stooq via pandas-datareader (personal use) | Survivorship-bias note; delisted gaps logged | Delisted history isn't free; acceptable for a hobby study if stated |
| Paper ledger / portfolio accounting | (Beancount *design*: immutable dated entries, lots) | Append-only SQLite/DuckDB `trades`, `corporate_actions`, `nav_daily`, with a `fund_id` per parallel fund | Engines add weight and still leave corporate actions to us |
| Corporate actions | edgartools (8-K items 3.01/5.03/2.01, Form 25), provider split fields | Event table + apply rules (reverse split, delisting, cash or stock merger, ticker change keyed on CIK) | No open feed; small biotech needs explicit handling |
| Performance stats | **empyrical-reloaded**, **QuantStats** (Apache-2.0) | – | Light, standard, well tested |
| Event study | statsmodels, pandas (+ alphalens-reloaded optional) | Market-model CAR script | Stale event-study packages; the method is simple |
| Trial data | CT.gov API v2 (direct), **AACT** for bulk SQL | Small httpx client, daily snapshot diffs | pytrials is stale; the API is simple |
| Trial base rates | Wong-Siah-Lo 2019 tables (CC BY 4.0) | Lookup table by phase × therapeutic area | Open and citable; ML models are stale or non-commercial |
| Outcome-prediction ML | (none; watch CT Open) | – | TOP non-commercial, CTO circular (stock-price labels), all leak into LLM pretraining |
| Catalyst calendar | – | LLM extraction from 8-Ks/PRs (EDGAR) + CT.gov completion dates, with source URLs | Open calendars don't exist; commercial ones are closed |
| SEC filings / financials / insiders / 13F | **edgartools** (MIT) | – | Best maintained; fair-access compliant |
| Literature | **Biopython Entrez**, **pyalex**; Europe PMC/bioRxiv via httpx | – | Mature, open |
| Entity glue (ticker↔CIK↔sponsor↔drug↔NCT) | SEC JSON, OpenFIGI, Wikidata, GLEIF, ChEMBL, GSRS, Open Targets | `company_alias` + `asset` tables, fuzzy match + one-time human check | No open sponsor↔ticker dataset exists; it's the core IP of the project |
| Agent tool access | cyanheads MCP servers, edgartools MCP (for interactive research) | Snapshot-passing for production decisions | Reproducible logging beats live browsing |
| Storage | SQLite/DuckDB (public domain / MIT) | Schema | ArcticDB is BSL and overkill |
| Data platform facade | (OpenBB v5 Apache-2.0, optional) | – | Not needed for one or two providers |

## Open items / unverified

- Stooq terms; free-tier details for Tiingo, Massive and Finnhub (delisted tickers, redistribution).
- ClinicalTrials.gov terms and API rate limit; AACT licence terms.
- OpenBB → OpenBQ / FINOS stewardship details (read the founder post); is Workspace now fully open?
- Licence of TrialBench data and of CT Open question sets; BIO/Informa report reuse terms.
- Wikidata property IDs, DrugCentral licence, GLEIF CC0: from memory.
- Hugging Face was not searched for catalyst datasets.
