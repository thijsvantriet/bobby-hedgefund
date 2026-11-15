# Overnight research brief (2026-11-15)

You run unattended overnight (Claude Fable, auto mode). The owner is asleep: do not ask questions, decide sensibly and write
your assumptions down. Read CLAUDE.md, README.md and docs/IDEA.md first.

## Goal
Two research reports that let the owner and a later spec session decide what to reuse and which data to collect. Research only:
no product code, no installs, no sign-ups, no paid services, no accounts, no real trading anything.

## Report 1: docs/research/OPEN-SOURCE.md - don't reinvent the wheel
Map existing open-source projects that could be reused or learned from, for each: what it does, licence, last release/commit
and activity, maturity, what we could reuse (as library, as design pattern, or not at all), and fit for a forward-running,
paper-money, biotech-focused multi-agent fund on a home server (Docker, Python/uv). Cover at least:
- multi-agent LLM trading/"hedge fund" frameworks (TradingAgents, virattt/ai-hedge-fund, FinRobot, FinGPT, FinMem, FinAgent, others you find)
- financial data platforms and research toolkits (e.g. OpenBB, Qlib, FinRL, others)
- paper-trading / portfolio-accounting / backtesting engines (e.g. LEAN, NautilusTrader, vectorbt, backtrader, Zipline-reloaded)
- biotech-specific open tools: catalyst calendars, clinical-trial parsers/NLP, trial-outcome models and datasets (TOP/HINT, CT Open),
  SEC/EDGAR parsing libraries, PubMed/bioRxiv clients
- open forecasting/LLM-trading benchmarks and how they avoid look-ahead bias
End with a build-vs-reuse table and a recommended stack (state clearly what is closed/proprietary; the owner prefers open source).

## Report 2: docs/research/DATA-SOURCES.md - the wide variety of information streams
A catalogue of information streams relevant to small and mid-size listed biotechs. For each source: what it contains, access
(API, bulk download, RSS, scraping), cost, licence / terms of use (may automated personal use? attribution?), history depth,
update frequency and delay, data quality, effort to integrate, and value for this fund (high/medium/low, with why). Think wide, e.g.:
- clinical: ClinicalTrials.gov, EU CTIS, WHO ICTRP, other national registries (China, Japan), trial result postings
- regulatory: openFDA, FDA approvals, advisory committee calendars, PDUFA dates (where do they come from openly?), EMA/CHMP,
  Federal Register, Orange/Purple Book, FDA warning letters / inspection data, CMS / drug pricing (IRA negotiation)
- company: SEC EDGAR (10-K/10-Q, 8-K, S-3/ATM shelf, 424B, Form 4, 13D/G, 13F, full-text search, XBRL financials), press releases,
  investor presentations, earnings calls (transcripts vs webcasts + local transcription; terms!)
- science: PubMed, Europe PMC, bioRxiv/medRxiv, OpenAlex, conference abstracts (ASCO, ASH, ESMO, AACR...), patents (USPTO, EPO, Lens)
- market: prices and volume, options / implied volatility around catalysts, short interest (FINRA), borrow data, index changes,
  ETF holdings (ARKG daily, XBI/IBB), 13F of biotech specialist funds
- news, sentiment, social: GDELT, Reddit/StockTwits, news APIs; M&A and licensing deals; China out-licensing
- macro and policy: interest rates (FRED; biotech is rate-sensitive), BIOSECURE-type legislation, tariffs, FDA staffing/policy
- alternative data: job postings, web traffic, Google Trends, KOL activity, anything clever you find
End with: a top-10 to build first (value per effort), sources to avoid (terms, cost, quality), and what needs the owner's decision.

## Also write
- docs/research/SUMMARY.md: one page in plain language (the owner is a biotech scientist, not a software or finance professional):
  the key findings, the recommended stack, the first data streams, and open questions for the spec interview.

## How to work
- Primary sources (official docs, repos, terms pages, papers) over blogs. Every claim gets a link. Mark anything unverified.
- You may use `researcher` subagents (Opus) in parallel for separate topics; brief each narrowly.
- You may make a few small read-only test calls to free public APIs to confirm they work (respect rate limits, tiny samples,
  no bulk downloads). Never send the owner's name or email to any service; if a source demands contact details
  (e.g. an e-mail in the User-Agent), do not test it, just note the requirement.
- Do not run code from cloned repos; read them (GitHub pages, `gh` API) instead.
- Save and commit progress after each major section (branch `research-overnight`), so an interruption loses little.
- When done: push the branch, open a PR (do not merge), add a Status line in README.md, and end with a short summary.
