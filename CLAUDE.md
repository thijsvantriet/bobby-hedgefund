# Biotech agents - briefing for Claude

Read README.md first: "Status" and "Next step" are this project's log and roadmap. The brainstorm that started it: docs/IDEA.md.
Specs: docs/SPEC.md (once written); decisions: docs/decisions/ (ADR format, use the design-decision skill).

## Rules
- PAPER MONEY ONLY. No broker connection, no real orders, ever, unless the owner explicitly decides otherwise in an ADR.
- No look-ahead: agents are only tested forward in real time. Historical data is for event studies and a case library, never to
  score the agents (the models already know how past cases ended).
- Every agent decision is logged with its thesis, the data it saw and a timestamp; logged decisions are never edited afterwards.
- Token costs: a hard monthly cap, set in the spec; measure in a pilot week before going live.
- Data sources: open/official APIs first; check terms of use before automating any download (earnings-call webcasts, fund holdings).
- Long-running services: compose file in ~/server/<name>/compose.yaml (read ~/server/CLAUDE.md first); scheduled jobs as systemd user timers in this repo.
- Python with uv. Work on a branch, open a PR; bigger changes get a `reviewer` subagent review before they count as done.
- Master to-do list: Home Assistant `todo.home_todo`; keep only detail here in the README.
