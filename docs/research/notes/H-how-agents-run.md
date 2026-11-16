# H. How the agents could run: API or subscription sessions

Checked on 2026-11-16 against the official Claude Code documentation and Anthropic's terms, by a documentation
agent. Input for the spec. Limits and terms change: check again before building.

**Owner's direction, 2026-11-16: option E, sessions opened by hand.** To be worked out and recorded in the spec.

## Options

| Option | Reads files on this machine | Runs without the owner | Allowed? |
|---|---|---|---|
| A. API key, started by a timer | Yes | Yes | Yes, clearly: automated use is what the API is for. Paid per use; a spending limit can be set |
| B. Subscription login, started by a timer (`claude -p`) | Yes | Yes | **Unclear.** The non-interactive mode and a long-lived login for scripts are documented, but the terms describe subscription logins as meant for "ordinary use" and the consumer terms forbid automated access unless explicitly permitted. Ask Anthropic before relying on it |
| C. Cloud scheduled task | No: each run starts from a fresh copy of a GitHub repository | Yes | Yes, on subscriptions. At most once an hour; uses the normal subscription limits; a research preview, so it may change. The data would have to be in a repository, which our sources' terms forbid for a public one |
| D. Scheduling inside an open session | Yes | Only while the session stays open | Yes, but recurring tasks expire after seven days and missed runs are not repeated: unfit for six months |
| E. The owner opens a session by hand | Yes | No | Yes: ordinary use |

## Other facts
- Subscription limits: a five-hour limit and a weekly limit, shared between all use of Claude; the strongest model
  has its own weekly limit on some plans. Exact numbers are not published in the pages that were read.
- Seeing usage: `/usage` in a session shows how much of the limits is used (approximate). There is no exact
  "this run used X" figure for subscriptions.
- A subscription login expires and must be renewed; an unattended job stops when it does.
- A subscription that belongs to an organisation (a team plan) follows that organisation's rules as well.

## Sources
- Scheduled tasks: <https://code.claude.com/docs/en/routines.md>, <https://code.claude.com/docs/en/scheduled-tasks.md>,
  <https://code.claude.com/docs/en/desktop-scheduled-tasks.md>
- Non-interactive mode and logins: <https://code.claude.com/docs/en/headless.md>, <https://code.claude.com/docs/en/authentication.md>
- Terms: <https://code.claude.com/docs/en/legal-and-compliance.md>, <https://www.anthropic.com/legal/consumer-terms>,
  <https://code.claude.com/docs/en/agent-sdk/overview.md>
- Limits and usage: <https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan>,
  <https://code.claude.com/docs/en/costs.md>
