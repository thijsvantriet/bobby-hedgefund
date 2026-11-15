# Idea and brainstorm (2026-11-15)

Started from a WallStreetBets post about Singapore export data (NODX) as a leading indicator and "The Big Short"-style edge hunting.
Not yet decided: everything here is input for the spec interview.

## Direction so far (owner)
- Paper portfolio, returns compared with indices: XBI (equal-weight biotech), IBB / Nasdaq Biotech, IWDA (the owner's real
  fund, the "do nothing" baseline), ARKG (publishes holdings daily), biotech specialist hedge funds via 13F (quarterly, 45-day lag).
- Focus: biotech/pharma, including listed AI-biotechs (Recursion, Schrödinger, Absci, AbCellera, Relay; Insilico status to check).
- **Fully agentic, like a normal biotech fund** (owner correction): agents are NOT a trial-outcome prediction model. A statistical
  success estimate is one input; agents add drug history, drug class, trial design, company cash and management, what the
  price already implies, and then make a sized financial decision.
- Universe (proposed): small and mid-size biotechs (~$300M-$10B), with a floor on size and daily volume; big pharma as context
  (acquirers, competitors). Long only in version 1. Subtract a realistic trading cost per paper trade.
- Several fund setups in parallel, sharing one analyst layer (analysts run once per company; only the decision layer differs):
  e.g. careful, aggressive, debate-heavy, plus a no-AI rule-based baseline.

## Investment thesis per trade (fixed template)
Claim; variant perception (what we believe that others don't, and why); catalyst + expected date; numbers (rNPV / implied vs
own success probability); risks and "we sell if…"; position size. Theses are scored separately from returns (did the catalyst play
out as expected, were exit rules followed), and the owner can review them like an investment committee.

## Proposed team (TradingAgents-like, biotech-specific)
Science analyst, clinical/regulatory analyst, financial analyst (cash, dilution, valuation), market analyst (price, what is priced in,
news, competitors), bull and bear researchers, risk manager (max per stock, not too many readouts at once), portfolio manager.

## Proposed variant perception of the fund
Big funds cannot put meaningful money into small biotechs, so hundreds get little analyst coverage; agents cost almost nothing per
company and can read every filing and trial update of those. Geopolitics left out of version 1 (vague, hard to verify).

## Data sources (candidates)
ClinicalTrials.gov API, openFDA + FDA decision (PDUFA) dates, SEC EDGAR (10-Q/10-K, 8-K, Form 4 insider trades), PubMed /
Europe PMC / bioRxiv, conference abstracts, daily prices (financial-dashboard already fetches prices), earnings-call webcasts
(transcripts usually licensed; local transcription with Whisper possible, terms to check).

## Sample size and costs
- ~150-250 companies watched, ~20-30 positions; score every decision, not only the portfolio total. Six months only shows big
  differences between setups.
- Rough cost estimate (API prices 2026-11: Opus 5.5 $4/$20 per M tokens, Haiku 5.5 $0.10/$0.50, batch -50%, cache reads 0.1x):
  deep analysis ~$1-1.50 per company; daily Haiku news screen pennies; total ~$40-150/month depending on deep dives. Measure in a
  pilot week; hard monthly cap. API billing is separate from the Claude subscription.

## Prior-art check (researcher agent, 2026-11-15)
- Role-based frameworks exist, backtest-only: TradingAgents (Tauric Research, Apache-2.0, https://github.com/TauricResearch/TradingAgents),
  virattt/ai-hedge-fund (MIT, educational). FinMem, FinAgent (papers).
- Live tests: Nof1 Alpha Arena (closed, real money, 2025; wildly mixed results, secondary sources only). StockBench (arXiv 2510.02209):
  risk-adjusted gains but not total-return wins. FINSABER (arXiv 2505.07078): LLM edge disappears over 20 years; too cautious in bull,
  too aggressive in bear markets. Look-Ahead-Bench (arXiv 2601.13770): most agents fail after their knowledge cutoff.
- Biotech: CT Open (https://ct-open.net/, live trial-outcome challenge, CC BY 4.0) could be an optional side benchmark. No public
  live biotech-specific agent fund found: that is the novel part.
- Pitfalls: look-ahead/memorisation, non-deterministic runs (log everything), overtrading, ignored trading costs, made-up data.

## Background discussed
- Why biotech feels like gambling: outcomes unknowable until human trials (~90% fail); "paradox of skill" (Mauboussin): skilled
  players cancel out, leaving luck; binary single-asset companies. Links to the owner's AI & biology essay (verification cost).
- Martin Shkreli as cautionary tale (small-biotech shorting, fraud conviction 2017). Small-cap traps: dilution, reverse splits,
  pump-and-dump, short-seller reports.
- Historical analysis: event studies (plain statistics) and a case library of missed warning signs; not to test the agents.
