---
name: bobbyhedgefund-day
description: The daily round of Bobby Hedgefund (paper money; pilot). Only the owner starts it, by typing /bobbyhedgefund-day in a fresh session. Never start it yourself.
disable-model-invocation: true
allowed-tools: Bash(uv run bobby-session *)
---

# The daily round of Bobby Hedgefund

**Paper money only. Nothing here is investment advice, and no real money is traded.**

The round has started. Before you read this, a script did step 1: it checked that this is a fresh session and
that last night's jobs ran, wrote down the start time and the data cut-off, and built the session folder. Its
output:

```!
uv run bobby-session start --session-id "${CLAUDE_SESSION_ID}"
```

If that output starts with `NOT DONE`, the round did not start. Show the owner that line and stop: do nothing
else, and do not try to repair anything.

## Your part

You are the leading session. **You decide nothing.** You run the round's commands one at a time and start the
agents they name. Scripts do everything that counts: they read the agents' answers from the agents' own records,
check the limits, write the log and publish.

Rules, and Claude Code itself refuses most of what breaks them while the round is active:

- Run only `uv run bobby-session <step>`, one command at a time, nothing joined to it.
- Start an agent **only** with the exact `PROMPT:` sentence a command printed, with the agent type it printed,
  in the background. Add nothing to the sentence. Give no model and no effort (unless the line says so).
- Start each task once. Never start a task again because its answer did not suit or did not come.
- Do not send a message to an agent, and do not stop one, unless a command says the time for its step is over.
- Do not read files of the session folder or the agents' answers yourself, and do not change any file.
- Do not summarise, correct or pass on an agent's answer. What an agent says back to you is not used.
- If a command prints `NOT DONE`, show the owner that line and stop.

## The steps

Each command ends with a line `NEXT:` that names the next command. Follow those lines; the order is:

1. `uv run bobby-session book` (step 2: fills, company events and values since the last session)
2. `uv run bobby-session screening` (step 3). It prints the agents to start. Start them all at once, in the
   background, and then run `uv run bobby-session collect screening` right away: that command does the waiting.
3. `uv run bobby-session analysts` (step 4), start what it prints, then `uv run bobby-session collect analysts`.
4. `uv run bobby-session debate` (only does something when the Debate fund runs), start what it prints, then
   `uv run bobby-session collect debate`; repeat `debate` until it says `NEXT: bobby-session managers`.
5. `uv run bobby-session managers` (step 5), start what it prints, then `uv run bobby-session collect managers`.
6. `uv run bobby-session decide` (step 6: from here the day's records are final)
7. `uv run bobby-session publish` (steps 7 and 8)
8. `uv run bobby-session end` (step 9)

Never wait for agents by yourself. A `collect` waits up to a minute and a half; when it says that answers may
still come, run the same `collect` again, and keep doing that until it prints `NEXT:`. When the time for a step
is over it stops waiting by itself and counts what is missing as late, so an agent that hangs cannot hold the
round. `uv run bobby-session clock` shows the minute of the round. The hard stop is minute 45.

## At the end

Show the owner, word for word, what `uv run bobby-session end` printed: it is the summary of the day. Then stop.
This session has done its round; tomorrow's round starts in a fresh session.
