# 0009. Agent team: roles, models, how versions are logged, repeated decisions
Date: 2026-11-18
Status: accepted (2026-11-19, the owner merged it with the recommendations under "Open points for the owner")

## Context
The spec fixes who is on the team and which model each role gets (`docs/SPEC.md`, section 3), and record 0003
fixes that the agents run inside one session a day, without web access, reading only prepared files. Left to this
record, and needed before the pilot:
- how a role becomes a file that Claude Code really obeys (model, effort, tools), checked against its documentation;
- how the exact model and prompt version of every agent run get into the log **by script from the session's own
  records, not from what a model says about itself**;
- how the leading session (the conversation that starts the agents) is kept from steering a decision;
- how the "three runs, two of three" rule of the spec works exactly;
- what could not be confirmed from documentation and must be checked in the pilot.

These are costly to change later: the log stores model details in every decision record, and a comparison between
funds only means something if every fund's decisions were made under the same, recorded conditions.

Requirements, from the spec and records 0003, 0004 and 0007: no web access and no command line for agents; agents
read only files saved before the data cut-off; numbers are computed by scripts; nothing computed from prices, and
no market value or per-share figure, may end up in public text; the session takes 20-30 minutes with a hard stop
at 45; one session may use at most half of a five-hour usage limit.

## What the documentation says (read 2026-11-18, Claude Code 2.1.327)
- **An agent file can fix the model and the effort.** The fields `model` ("a full model ID such as
  `claude-opus-5-5`") and `effort` (`low`, `medium`, `high`, `xhigh`, `max`; "overrides the session effort level")
  exist. A misspelt field is ignored without an error, so a test must check the spelling.
- **An agent file can be denied web tools.** The field `tools` is a list of allowed tools; without it an agent
  "inherits every tool". With `tools: Read, Grep, Glob` an agent has no command line, no web search, no web fetch
  and cannot start agents of its own.
- **The start of an agent can override the file.** Whoever starts an agent may pass a model or an effort for that
  one run, and that wins over the file. So the file alone proves nothing: the run's own record must be read.
- **A check can run before every tool use** (a "hook"), it is told which agent is calling, and it can refuse. Such
  a check can be written in the agent file itself, and then exists only while that agent runs.
- **Every agent run has its own record on disk**: one file per run in the session's folder `subagents/`, with a
  small file next to it naming the agent type. Looked at on this machine (field names only): every answer line
  carries the exact model name, the effort, the Claude Code version and how much text went in and out (counted in
  "tokens", the unit the usage limits are measured in). The record is written with a small delay.
- **What an agent receives besides its task:** its own instructions, the project's briefing files (unless the file
  sets `omitClaudeMd: true`), and a snapshot of the repository's git status with the latest commit titles. The last
  cannot be switched off per agent.
- **A new `.claude/agents/` folder is only noticed after a restart** of the session; later changes to files in it
  are picked up within seconds.
- **If a model cannot be used**, Claude Code can switch an agent to another model, and says so in the agent's
  report.

## Options considered

**How the report of one company is written**

| Option | For | Against |
|---|---|---|
| **A. One agent per analyst role, each writes one section; a script joins the sections** | The roles of the spec, each scored on its own forecasts; runs side by side, so four companies fit in the 18 minutes of step 4; no extra model run | About four runs per company |
| B. One analyst agent per company that plays all roles | Cheapest | One long run per company; no score per role; the spec's team is gone |
| C. As A, plus an editor agent that rewrites the sections into one text | Reads better | One more model run per company that adds no information and can drop a caveat |

**Where an agent's answer is taken from**

| Option | For | Against |
|---|---|---|
| The leading session passes it on | Nothing to build | The leading model retypes or summarises: it can change a number or a word unnoticed, and it has read things the agents may not |
| The agent writes its own file | Direct | Needs a writing tool, and with that a way to write anywhere |
| **C. A script reads the answer from the agent's own record** | The same record gives model, effort, tokens and every tool the agent used; nobody retypes anything | Depends on the layout of Claude Code's records, which can change with a version |

**Repeated decisions** (spec: a new position is decided three times, opened when two of three say buy)

| Option | For | Against |
|---|---|---|
| **A. Every portfolio-manager round runs three times, always** | The spec's rule exactly; the agreement between runs is measured every day | Three runs of the strongest model per fund per day |
| B. A second and third run only when the first wants to open a position | Cheaper on quiet days | The first run becomes a veto: a position that runs two and three would both open is never considered. Not the spec's rule |
| C. Three runs per candidate company instead of per round | Finer | Many more runs; a manager must weigh companies against each other in one view |

Majority voting over independent runs is the standard way to use a model's own inconsistency as a signal
(Wang and others, 2022); the research for this project asked for the spread between runs to be recorded
(`docs/research/OPEN-SOURCE.md`, 3.5, rule 5).

## Decision

### 1. The files
One file per role in `.claude/agents/`, named `bobby-<role>.md`:

| File | Model | Effort | Runs |
|---|---|---|---|
| `bobby-screening` | `claude-haiku-5-5` | low | Once per group of about 25 companies with news |
| `bobby-screening-check` | `claude-opus-5-5` | high | Weekly, on 20 random companies marked "no" |
| `bobby-science-analyst`, `bobby-clinical-analyst`, `bobby-financial-analyst`, `bobby-market-analyst` | `claude-opus-5-5` | high | Once per company in deep analysis |
| `bobby-results-reader` | `claude-opus-5-5` | high | Only when a results announcement is among the new items |
| `bobby-bull`, `bobby-bear` | `claude-opus-5-5` | high | Debate fund only, two rounds at most, once per session: all three runs of that fund's manager read the same debate |
| `bobby-pm-careful`, `bobby-pm-bold`, `bobby-pm-debate` | `claude-fable-5-2` | high | Three times per session (point 4) |

- **Full model names, never the short names** (`opus`, `fable`): a short name moves to a new model the day one is
  released, and the file would not show it.
- Every file has `tools: Read, Grep, Glob` and `omitClaudeMd: true`, and names the reading check of record 0003.
  A test fails when a file has no tool list, lists any other tool, or has a field that is not in the documentation.
- Companies without any new item are marked "no news" by the script and are not sent to the screening model.
- **Option A for the report:** each analyst returns one section; a script joins them into the one report per
  company. No editor agent.
- Every agent's answer has a fixed form (a block of named fields that a script can check): a report section, a
  forecast (the event, the date, the probability, whether it is a make-or-break result), a screening answer, or a
  decision with the thesis form of the spec, section 5. It ends with a list "what I lacked", which the script
  collects for the review after the pilot (record 0003).
- **Which catalysts have resolved** (spec, section 1, step 4) is recorded by the clinical and regulatory analyst,
  for every kind of catalyst (a trial result, an FDA decision). For a results announcement the results reader adds
  its reading of the result.
- The reports themselves stay in the data folder: they hold numbers from prices and text from sources. Public are
  only the forecasts, the decisions with their thesis, and the day page made from them.
- The instructions tell every agent: in a forecast or a thesis, no prices, market values or per-share figures, and
  nothing worked out from a price (a rise or fall in percent, "trades below its cash", a ratio to the market
  value); the numbers part of a thesis is filled in by script (record 0004). Name sources by their number in the
  session's inputs list; a quote is at most two sentences.

### 2. How the versions are logged
A script reads each agent run's own record. It waits until the record holds the final answer (records are
written with a delay); a run without a final answer by minute 38 is "no answer". It stores, for the log:
- the exact model name and the effort **as recorded for the run**, and the Claude Code version;
- the fingerprint of the agent file and of the task text, and the git commit of the code.

The tokens and the times of each run are kept in a private file in the data folder, per role, for the usage
figures of the pilot. Only percentages of the usage limits are published (spec, section 7).

**All records of a session, the agents' included, are copied to the data folder** (spec, section 3): at the end
of the session, and completed at the start of the next one, because Claude Code writes them with a delay and
removes them after 30 days. The fingerprint of the complete copy goes into the next session's first log record.

**When the recorded model or effort differs from the agent file**, the answer is rejected, with one exception.
If a run fails because its model cannot be used, the script (not the leading session) allows one new start of
that task on the next model down (Fable, then Opus, then Sonnet). That run is logged as **substituted**, with both
model names. If the three runs of one portfolio manager did not all use the same model, the whole round is marked
in the log. Without Haiku the screening is skipped that day and the rotation of the spec decides who is analysed.

### 3. The leading session cannot steer
The leading session only starts agents and runs scripts. It decides nothing. These rules guard against slips and
shortcuts by the leading model; they are not a lock against a model that sets out to cheat, because the leading
session has a command line. What makes that visible afterwards is the complete copy of the conversation (point 2).
- **An agent is started with exactly a prepared task text.** The script writes one task file per run. A check at
  the start refuses any other text, any agent type that does not belong to the task, and any model or effort given
  by hand. The same is checked again afterwards from the agent's record.
- **A task file cannot be swapped.** The script stores the fingerprint of every task file at the moment it writes
  it, and makes the session folder read-only. A start is refused, and an answer rejected, when the task file no
  longer has that fingerprint. The round is refused when an agent file or a check script differs from the commit
  the session runs. While a round is active, the leading session's own tools for changing files are refused.
- **Only the first start of a task counts**, and every start is noted. A task cannot be run again until the answer
  suits. (The one exception is the model fallback of point 2, which the script allows and logs.)
- **An agent record with a second incoming message is rejected.** Nothing can be whispered to a running agent.
- **The answer is taken by script from the agent's own record** (option C), never from what the leading session
  passes on. An answer that cannot be read is "no decision" (for an analyst: no section); nothing is retyped or
  repaired by hand.
- **The script reads back which tools the agent used.** Anything but reading inside the session folder rejects
  the answer. This is a second layer behind the tool list and the reading check. It is the only layer in the one
  case where the agent files cannot be used: a try-out in the session that has just created them (Claude Code
  notices a new agents folder only after a restart).
- The portfolio managers' task files are put together by script from the collected reports.

### 4. Repeated decisions: option A
- Each AI fund's portfolio manager runs **three times per session**, independently, on the same task text; the
  runs are numbered beforehand.
- **A new position is opened only when at least two of the three say buy, at the smallest size among those that
  do.** A position is new when the fund does not hold the company and has no buy order waiting for it (record
  0005, point 2). The thesis that is logged is the one of the run with that smallest size (the lowest-numbered one
  if two are equal), so size and thesis always come from the same run.
- **Everything else (add, reduce, sell, do nothing) follows run number 1**: the number given beforehand, not the
  run that happens to finish first. If run 1 has no readable answer, the lowest-numbered readable run takes its
  place, and the log says so.
- The two rules work side by side. If run 1 sells company X and runs 2 and 3 both want to open company Y, X is
  sold and Y is opened. The orders of both rules together form the fund's one list for the day, and the risk
  limits are checked on that list (spec, section 1, step 6).
- **One readable answer is enough for selling, not for buying.** With a single readable run its add, reduce and
  sell orders count (a missed sell costs most; spec, section 1), but no new position is opened. Without any
  readable answer the fund gets "no decision today".
- The log records all three answers and whether they agreed.
- Forecasts are not repeated (spec, section 3).
- A run that has not answered by minute 38 counts as "no answer".

### 5. Checks on written text
Fixed here because the agents' instructions and the log's checks (record 0004, point 2) must agree:
- **A long quote** is more than 40 words in a row copied from one source file, or more than two such copies of
  over 15 words in one text. The check replaces it by "[removed]".
- **A market value of a company, a figure per share, and anything worked out from a price** (a rise or fall of a
  share in percent, a return, a ratio to the price or the market value, "trades below its cash") in written text
  is always sealed (record 0007, point 6). **Any other amount of money** is sealed unless the same amount stands
  in a filing among the session's inputs. In doubt it is sealed. The check is a list of patterns, so it can miss
  an unusual wording; that is why the agents are told the rule as well, and why the day page is read once more by
  the same check before it is published.
- **A forecast whose event is defined by a price** ("the share is above X on date Y") is refused: its outcome
  could not be published.

## Differs from the spec
1. Section 3 says "each agent is a file … with its model and effort fixed in the file". True, but a start can
   override the file, so the log takes both from the run's record and compares them with the file.
2. Section 3, repeated decisions: the spec speaks of "a decision to open a new position". Here the whole round of
   a portfolio manager is run three times, because one run decides about all companies at once; the two-of-three
   rule is applied per company. Other actions follow run 1.
3. Section 3, the weekly check on the screening, gets its own agent file.
4. Section 1: agents get a snapshot of the repository's git status that cannot be switched off. It shows file names
   and commit titles of this public repository, nothing from the data folder.
5. Section 4, the universe and the "same pool for all" rule: the companies that are in the universe through the
   XBI fund only (six at the run of 2026-11-18; counted again at every monthly re-run, record 0006) get no deep
   analysis. So they are never on the covered list, never in a Dice draw, and the rotation of section 1 skips
   them (open point 2).
6. Section 3 says a session "uses the next one down" when a model is not available. Here that is one new start of
   the task, allowed and logged by the script.

## Open points for the owner
Each has a default that the pilot runs with. Decided 2026-11-19: the owner took all three recommendations.
1. **Three runs always (option A), or only when the first run wants to buy (option B)?** Recommended: A, as the
   spec says. The pilot measures what it costs; the spec already lists "no repeated decisions" as the second step
   when usage is too high.
2. **The six companies that are in the universe through the XBI fund only** (record 0006, update 2026-11-18).
   A decision record may never hide the company (record 0004, point 2), so a fund that bought one could not be
   published. Recommended, and the default: they get no deep analysis, so they are never on the covered list,
   never bought, never drawn by the Dice funds and never forecast. They stay in the private universe file.
3. **The limit for a long quote** (point 5: 40 words). Recommended: keep; it is about two sentences.

## Consequences
- A model or prompt change is a changed file with a new fingerprint, visible in the log from that day.
- The usage figures of the pilot come from the same records, per role, without anybody counting.
- Three runs of the strongest model per fund are the most expensive part of a session after the analysts.
- Everything in point 3 rests on how Claude Code stores its records and runs its checks. A new version can change
  that. The script refuses a record it does not understand; it never guesses.
- An agent cannot ask a question back. What it lacked is only seen afterwards, in "what I lacked".
- The pilot does not exercise GitHub's receipt time or the independent timestamp of record 0004: the pilot log
  stays in the data folder (record 0004, point 3). Both are tried once before the funds start.

**To check in the pilot** (could not be confirmed from documentation):
1. that the effort recorded for a run equals the effort in the file;
2. that Fable runs as an agent inside a session, and that the exact names `claude-fable-5-2` and
   `claude-haiku-5-5` are accepted (a wrong name must fail, not quietly become another model);
3. that an agent with the tool list above really has no tools that reach outside services (its record shows every
   tool it used);
4. that the reading check fires inside an agent and names it;
5. that `/clear` is reported as a fresh start with a new session number (record 0003);
6. what an agent actually received at its start (briefing, memory, git status), read once from a record;
7. whether the usage percentages reach a script through the status line, the one place Claude Code gives them to
   (spec, section 7).

## Update 2026-11-18: how the files and the checks are built
- **One role table** (`src/bobby_hedgefund/session/roles.py`) holds every role's model, effort and full text; the
  twelve files in `.claude/agents/` are checked copies of it. Tests check, per file: only documented field
  names, the tool list `Read, Grep, Glob`, a full model name, the effort, no project briefing, the reading check,
  and that the example answer in the file is one the script accepts.
- **The reading check sits in each agent file** (as a check before every tool use), not in the project's
  settings, so it exists only while that agent runs. It follows links before it judges a path, refuses a search
  without a folder, and refuses when no round is active.
- **Five more checks are in the project's settings** (`.claude/settings.json`): the start of an agent; changes to
  files by the leading session; sending a message to an agent or stopping one; the command line, which during a
  round is only for the round's own commands, one at a time; and a note of how each session began. The first
  four do nothing unless the data folder holds a marker that names the running session and is younger than 90
  minutes (a marker that is too old, dated in the future or unreadable counts as none); the fifth only writes a
  line. So ordinary work in this repository is never touched by them.
- **The reading check refuses whatever goes wrong inside it**, also a fault of its own. It is started through
  `python3` by name; when the checks file cannot be found at all, `python3` itself ends with the code that
  refuses the tool. It lets one thing through besides reading: the tool an agent hands its report back with.
- **What belongs to one fund is closed to the others**: a portfolio manager can read its own task file and its
  own fund's holdings, not another fund's, and only the Debate fund's agents read the bull and bear cases. Nobody
  reads the list of all tasks.
- **Still not a lock.** The leading session could change the marker or these files between rounds, and what a
  check does not see it cannot refuse. Record 0009, point 3, says so; the copy of the whole conversation is what
  makes it visible afterwards.
- **A stand-in** (point 3): when the agent files cannot be used because they were made in the running session,
  the script writes the role's instructions into the task file and names the general agent, the model and the
  effort it must be started with; the start check accepts exactly that.
- **Answers** (`session/answers.py`): the last block in the fixed form counts (an earlier one is a draft),
  no other block may follow it (plain words after it are ignored, update 2026-11-23), no number with a decimal point, no field name twice; every list of sources has the one
  form (number and one sentence); at most five orders and one per company for a portfolio manager; "sell" is
  always the whole position, a part is a "reduce". A message about a refused answer says what is wrong, never
  what the answer said.
- **A thesis states a probability that can be scored**: that its catalyst turns out the way the thesis needs, by
  its date, not "that the thesis is right".

**Review.** A reviewer agent (Opus) ran the checks with made-up input and confirmed that ordinary work outside a
round is never refused, but said "fix first". Worked in: after a model fallback a task could be run again on the
original model; the reading check let a read through when the check itself crashed (any exit code but one does
not block); a marker dated wrongly never expired; a message to a running agent and the command line were not
covered; every agent could read every task file and so another fund's holdings; search patterns with braces and
file filters were not checked; a draft block in an answer threw the whole answer away; two different forms for
lists of sources invited a mistake that costs a whole run.
- Not confirmed by any test here, because they need a real session: that Claude Code runs these checks inside an
  agent and names the agent (pilot check 4), and that a check in an agent file applies to every tool.

## Update 2026-11-23: two fixes after pilot day 1

- **The reading check crashed on a search of the session folder itself.** Day 1: 9 of the 11 agents ran
  searches that named the session folder itself as their folder (a Glob of `**/*` or `companies/101/**`, a Grep
  for a company number). The check had no subfolder name to look at, crashed, and refused them as "the reading
  check failed (IndexError)": safe, because a crash refuses, but the agents could not tell what was wrong. Now
  such a search is refused with a message that names where to search instead (a folder such as
  `companies/<number>` or `round/reports`). No search from the top is allowed, whatever its pattern: the reviewer
  showed that a Glob pattern without a slash matches at any depth, and that Claude Code rewrites a pattern that
  starts with folder names, so a first version that judged the pattern let file names from `tasks/` and the
  funds' folders through. A backslash in a search pattern is refused too, because it can hide a folder name from
  the check (`t\asks`).
- **Plain words after the block of JSON no longer throw an answer away.** Day 1: an analyst ended with a list of
  what it left out and the files it read, after its block; the answer was refused and the company's report had
  three sections instead of four. Now plain words after the last block are ignored, as all words outside it
  already are (no script reads them). Another block after it, finished or not, is still refused, because then
  it is not clear which block is the answer. The risk accepted: an agent that changes its mind in words after
  its block is not heard; the block is its formal answer, and the agent files say so. Claude decided this (the
  owner left it to Claude); the agent files still say to write nothing after the block.

## Update 2026-11-27: fixes after the pilot week (days 1-5, Careful fund only)
What the five rounds showed, from the rounds' own records (`rounds/<day>/`: answers, refusals, `usage.json`), and
what changed. Each change has a test; options that were turned down are named.

- **A forecast without its list of sources no longer costs the whole answer.** Day 5: one analyst wrote a
  forecast without the `sources` field and its whole section was thrown away. An empty list was already allowed,
  so a missing list now counts as empty. Nothing is filled in; the section's own list stays required.
- **"Defined by a price" (point 5) was too wide.** Six forecasts on days 2, 4 and 5 were refused, all about a
  company event: "sold shares of common stock *under* the sales agreement", "an Equity Payment in common stock
  ... *under* the Equitization Option". Now "over", "under", "at least" and "at most" count only when a figure
  follows ("under $5"), and "up to" is an amount, not a move. A replay over all 121 forecast events of the pilot
  changes exactly those six. The rule itself stays: a forecast about the level or move of a share is refused.
- **A read the reading check refused no longer throws the answer away.** Day 4: a portfolio manager's long
  search result was kept by Claude Code in a file outside the session folder; the agent tried to read it, the
  check refused, and the second layer (the script that goes through the agent's record) counted the refused
  attempt and threw away the whole run. A call whose result is the check's own refusal (an error result in the
  check's words, written by Claude Code, not by the agent) read nothing and is now passed over; any other call
  outside the folder still rejects the run, so the second layer still holds when the check does not fire.
  Turned down: letting agents read those saved results. The same place holds the saved results of every agent
  of the round, of every fund. The refusal now says what to do instead (search a smaller folder).
- **Where to search is in the instructions.** 5 to 26 searches a day were refused because they started at the
  session folder itself. The shared instructions of every agent file now name the folders to search. The agent
  files changed with this; their new fingerprints are in the log from the next round.
- **An unchanged repeat of an open forecast is not written again.** 22 of the 100 pilot forecasts repeated an
  open one by the same role word for word, with the same date and probability, which would count one view
  several times. Such a repeat is noted in the day's notes and not written. A changed probability is written as
  a new record; how updates are scored is for the scoring record. The agent files say this too.
- **A lost screening batch gets one fresh run.** Day 0 and day 4: a screening answer without its block of JSON
  left a whole batch (25 companies) unjudged. When a screening answer is thrown away *for its form*, the batch
  gets one new task with the same text (`screening-NN-again`), started and judged like any other, before minute
  10 of the round. Not for an answer that broke a rule, and never a third run. This is a new run, not a repair:
  the first answer stays thrown away, and point 3 (a task is started once) still holds for each task.
- **The reason for a deep analysis names the catalyst's date** (until stream 5 brings a real calendar, the date
  of our nearest open forecast).

- **The weekly check on the screening is now part of the round.** It had an agent file but never ran: day 1
  was a "weekly" day and nothing happened. On a day with weekly extras the screening step also hands out one
  task (`check-screening`) to `bobby-screening-check`: up to 20 companies the screening marked "no deep look" in
  the seven days before, drawn by fingerprint of the day and the company number (anyone can draw it again), each
  with the lines of news the screening saw. Those lines are copied into the task file, because the folders of
  earlier days may not be read; their source numbers belong to their own day. The check is not told the
  screening's verdict. Its result (how many of the sample Opus would have sent to a deep look) is kept in the
  round's folder and in `usage.json`; the spec's rule (more than 2 of 20, two weeks in a row) is applied at the
  monthly review, not in the round. Its verdicts never count as screening verdicts. Measured on the pilot data:
  the first check (Monday 2026-11-30) has exactly 20 companies to draw from.

## Revisit
Revisit: by 2027-01, or after the pilot week, or when a new Claude Code version changes agent files, hooks or the
layout of session records, or when a new model replaces one named in a file.

## Sources
Read on 2026-11-18.
- Claude Code documentation: [agent files](https://code.claude.com/docs/en/sub-agents.md) (fields, what an agent
  receives, tool filters, fallback models, when files are loaded), [hooks](https://code.claude.com/docs/en/hooks.md)
  (input fields, checks in agent files, the start of a session and of an agent),
  [skills](https://code.claude.com/docs/en/skills.md), [status line](https://code.claude.com/docs/en/statusline.md),
  [model configuration](https://code.claude.com/docs/en/model-config.md)
- The records of earlier sessions on the owner's machine (field names only)
- Wang and others, [Self-Consistency Improves Chain of Thought Reasoning in Language Models](https://arxiv.org/abs/2203.11171) (2022; abstract read)
- The pilot week's own records (2026-11-23 to 27), summed up in `docs/pilot/PILOT-REPORT-2026-11.md`
- This project: `docs/SPEC.md`, sections 1, 3, 5 and 7; records 0003, 0004, 0006, 0007;
  `docs/research/OPEN-SOURCE.md`, 3.5 (rules 5, 6, 7 and 9); `docs/research/notes/H-how-agents-run.md`

Not verified: the seven pilot checks above; whether an agent's record always holds its first message word for
word; how long the layout of the records stays as it is.
