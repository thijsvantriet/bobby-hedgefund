# Bobby Hedgefund

A paper-money biotech fund run by a team of LLM agents, fed by open data (clinical trials, FDA, SEC filings, papers,
earnings calls), run forward on the home server for about 6 months and compared with XBI, IBB, IWDA and real biotech funds (ARKG, 13F filers).

## Status
2026-11-15: project named Bobby Hedgefund (repo and folder `bobby-hedgefund`, renamed from biotech-agents). Idea brainstormed with Claude (see docs/IDEA.md, incl. a prior-art check). Project folder created; no spec, no code yet.

2026-11-15: overnight research done (branch `research-overnight`, PR open, not merged): what to reuse, which data to collect, and a first look at past cases. Start with docs/research/SUMMARY.md; it ends with the open questions for the spec interview. No code, nothing installed.

## Next step
1. Interview + spec (docs/SPEC.md), in plan mode.
2. Historical study: event studies (how small-biotech prices move around readouts, FDA dates, financing) and a case library of
   "missed" situations; this decides which data sources to build first.
3. Build those data streams; start archiving ARKG daily holdings from day 1.
4. One-week pilot with one fund setup to measure real token cost.
5. Parallel setups live for ~6 months.
