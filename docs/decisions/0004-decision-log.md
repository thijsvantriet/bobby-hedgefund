# 0004. Decision log: format, fingerprint chain, publication and proof of time
Date: 2026-11-17
Status: proposed

## Context
The project's central promise is that every decision of every fund is public before the market can act on it and
is never edited afterwards (`CLAUDE.md`; `docs/SPEC.md`, sections 2 and 5). The log is where that promise is kept
or broken. Its format cannot be changed later without breaking the chain of fingerprints, so it is fixed before any
agent code is written.

The spec chose: one JSON Lines file per session day in `track-record/log/`; lines are only ever added; every record
carries the fingerprint (SHA-256) of the record before it, also across files; a small `HEAD` file guards the newest
end; one commit per day pushed straight to the main branch by a script; the main branch refuses rewrites; an
independent public timestamp is to be weighed. Left to this record: exactly what is fingerprinted, what GitHub can
really enforce, how the time of publication is proven, and how the log deals with things that may not be public
(prices, record 0007; text removed by the leak check).

The hard part, from the literature: **a chain of fingerprints proves nothing against its own author.** Whoever writes
the log can change an old record and recompute every fingerprint after it, and the `HEAD` file too. The chain only
becomes evidence when its newest fingerprint is handed, every day, to parties the author does not control.

## Options considered

**What is fingerprinted**

| Option | For | Against |
|---|---|---|
| **The exact bytes of the line as written** | Simple; nothing to interpret; the same as the archive (`docs/decisions/0001`) | Anything that rewrites the bytes breaks the check, for example a program that converts line endings |
| A standard "canonical" form of the JSON (RFC 8785) | Survives re-formatting | Only needed when others rewrite the data, and nobody does; an extra library; does not settle how accented letters are written |
| One fingerprint per day file | Even simpler | Shows that a file changed, not which record |

**An independent timestamp for the daily fingerprint**

| Option | What it proves | What is sent out | Depends on | Checking it years later |
|---|---|---|---|---|
| None: GitHub's own record of when it received the push, plus GH Archive (a public copy of GitHub's event stream, run by a volunteer) | The time to the second, as long as GitHub and that archive are believed | Nothing extra | GitHub; one archive | Through GitHub's service or the archive's files |
| **OpenTimestamps** (open source) | That the fingerprint existed before a certain block of the Bitcoin chain: within hours, not to the minute | Only a scrambled fingerprint | Nobody, once the proof is complete and stored | With free software, by anyone |
| Sigstore Rekor (open source, a public log) | The time of entry in that log | Fingerprint and a signature; **the usual way of signing publishes the signer's e-mail address for good** | The Sigstore project | With its tools |
| A timestamp service after the internet standard RFC 3161 (for example FreeTSA) | A signed time to the second | The fingerprint | One operator, trusted and alive | With standard tools and the saved certificates |

**Protection of the main branch on GitHub** (personal public repository, free plan)

| Option | For | Against |
|---|---|---|
| **A ruleset on `main`: no rewriting, no deleting, nobody exempt** | Available on this plan. Anyone can see that the ruleset exists and when it was last changed | The owner can switch it off; outsiders see that it changed, not what |
| The older "branch protection" setting | Does the same | Outsiders cannot see the setting at all |
| Also force every change through a pull request | Closes direct pushes | The daily publication must be a direct push; an exemption for it would exempt everything pushed with the owner's login |

## Decision

### 1. Records and fingerprints
- **JSON Lines**, one record per line, UTF-8, lines ending in a single line-feed. The layout of the spec:
  `track-record/log/<year>/<month>/<date>.jsonl`.
- **The fingerprint of a record is the SHA-256 of: the fingerprint of the previous record (as text), a line-feed
  (the character that ends a line), and the exact bytes of the line without its own final line-feed.** The first
  record uses a fixed, published starting value. The chain runs on across day files.
- Every record carries: the format version, its running number, its kind, the time, the fingerprint of the record
  before it.
- To keep the bytes stable on every computer: one fixed way of writing JSON; letters outside the basic English
  set written as codes; amounts as whole cents and percentages as text (never numbers with a floating decimal
  point, which different programs print differently); and a setting in the repository (`.gitattributes`) that stops
  git from converting line endings in `track-record/`.
- **`track-record/HEAD`** holds the newest fingerprint and the number of records. It catches a log that lost its
  last lines by accident.
- Nothing is edited: an outcome, a second thought or a found mistake is a new record that points to the old one
  (spec, section 5). A new format version applies from its first record on; old records are never rewritten.

### 2. Sealed fields: things that may not be public
Some content may not be published:
- **everything on the list in record 0007, point 6**: prices, share counts, amounts of money of a trade, trading
  costs, cash, and (until open point 1 of that record is settled) the values and returns of funds and index funds.
  That list is the only one; this record does not keep a second;
- **numbers in written text that come from prices** (a market value, a figure per share): see below;
- text that the leak check removes: a key, an address, a quote that is too long.

How it works:
- The **public record** holds, in place of that content, the word "sealed" or "[removed]" and **the fingerprint of
  the content** (mixed with a random value, so that a price cannot be guessed from it).
- The **content itself** and the random value are written to a private file with the same record number, in
  `~/bobby-hedgefund-data/log-private/`. One exception: a key or an address that the leak check removes is not kept
  anywhere.
- The public line is written **once** and never changed. If content may be shown later (for example after a yes
  from the price service), a new record reveals it, and anyone can check it against the fingerprint published at
  the time. Without such permission nothing is revealed.
- The fields that say what was decided (fund, company, action, size in percent, and the rule by which it will be
  filled) are never sealed and never touched by the leak check. A decision states the fill **rule**; the fill
  **day** is only known later and is stated in the fill record.
- **Written text is checked by a script before the line is written.** The thesis has a part "the numbers" that
  scripts fill in; its entries that come from prices are sealed automatically. In the free text the agents are
  told to use no prices, market values or per-share figures, and the script removes and seals any amount of money
  it cannot trace to a filing. In doubt it seals. The same check runs on the day page and the letters.
- Private files that contain prices fall under the deletion rule of record 0007. After such a deletion `verify`
  reports those fingerprints as "content deleted under record 0007", not as damage.

### 3. Publication
- A script makes **one commit per session for the day's decisions**: the day's lines, the day page and `HEAD`,
  pushed straight to `main` (spec, section 5). This is the commit whose receipt time counts.
- After it, the same script may make further commits that only **add new files** in `track-record/`: the timestamp
  proof (point 4), the weekly summary, the monthly letter, a new universe list. They never touch the log.
- The script refuses to commit anything outside `track-record/`, and refuses when an existing line would change.
  **GitHub cannot enforce the folder limit on this plan; the script and `bobby-log verify` do.**
- The script runs from the published main branch only (record 0003).
- Code and documents keep the route of a branch and a pull request. That is a working rule, not a lock.
- **Ruleset on `main`** (a set of rules that GitHub enforces on a branch): rewriting history (a "forced push") and
  deleting the branch are blocked, with nobody exempt. Switched on before the pilot.

### 4. Proof of time
Three layers, from precise to independent:
1. **GitHub's receipt time.** GitHub keeps, per push, the time it received it and the commit it contained; anyone
   can read this for a public repository. The script reads it at the next session and writes it into that
   session's first record (spec, section 2, point 4). The date inside a commit is not used: the sender sets it.
2. **GH Archive** records the same push independently of the owner. Nothing to build; it is named in the README
   as a way to check.
3. **OpenTimestamps on the daily `HEAD` fingerprint.** After publishing, the script asks for a timestamp of the
   new fingerprint and stores the small proof file in `track-record/timestamps/`, in a second commit right after
   the day's commit. The proof is completed some hours later, when it is anchored in the public Bitcoin record; the
   next session stores the completed version (a new file; the first one stays). Only a fingerprint
   leaves the machine. If the timestamp service cannot be reached, the day's publication still counts and the next
   session tries again.

Sigstore Rekor is **not** used: it would publish an e-mail address. A second timestamp from an RFC 3161 service is
left for later.

### 5. `bobby-log verify`
Re-reads every line, recomputes the chain, compares it with `HEAD`, checks the stored timestamps, and, on the
owner's machine, checks every sealed fingerprint against the private file. It runs at the start of every session;
anyone can run the public part on a copy of the repository.

## What this proves, and what not
- **Proven to anyone:** the log as it stands is one unbroken chain; each day's state existed no later than its
  Bitcoin-anchored timestamp (precise to a few hours).
- **Recorded by GitHub, and readable by anyone today:** the second at which GitHub received each day's commit. How
  long GitHub keeps this is not documented, which is why the other two layers exist.
- **Proven for sealed content:** that it was fixed at the time, once it is revealed. Until then it is not checkable
  by outsiders.
- **Not proven by the chain alone:** that the author never replaced the whole log. That rests on the outside
  records: a rewritten history shows up as a forced push in GitHub's public record, as a changed ruleset, and as a
  mismatch with every timestamp and every copy made earlier.
- **Not closed:** the owner can switch the ruleset off, and deleting and recreating the repository would erase
  GitHub's own record (the timestamps and GH Archive would still contradict a new history). The project's answer is
  that such a step is visible, and that it ends the experiment (spec, section 9).

## Differs from the spec
1. Section 2, point 7, "the main branch is set to refuse rewrites": true, but the owner can switch it off. The
   protection is that this is visible and contradicted by outside records, not that it is impossible.
2. Section 5, the script "refuses to change anything outside `track-record/`": only the script enforces this.
3. Section 5, "`HEAD` guards the newest end": against accidents and outsiders. Against the author the guard is the
   daily timestamp.
4. Section 1, steps 6 and 7: the leak check on the log's text runs **before** the public line is written, not
   after, so that a line never has to be changed. The decision fields are fixed first and are not touched by it.
   The page for the day is still checked afterwards.
5. Section 5: fill prices, share counts and the other content on the list of record 0007 are sealed, not shown.
6. Section 5, "one commit": the day's decisions are one commit; proofs, summaries and letters follow in commits of
   their own.

## Consequences
- A stranger can check the whole public log with one command and no account.
- Publishing depends on GitHub; the independent timestamp depends on volunteers' servers at the moment of
  stamping, and on nobody afterwards.
- The OpenTimestamps program is open source under the LGPL, a licence that asks for sharing changes to the program
  itself. It is used as a separate tool, not built into our code, so it does not change our MIT licence
  (`docs/decisions/0002`).
- The rule against numbers from prices in written text limits what a thesis may say; the agents' instructions
  (record 0009) must be written for it.
- Two files per day instead of one where something is sealed; `verify` needs the private files to check everything.
- Because whole numbers and text are used for amounts, every script that reads the log must convert them the same
  way; this gets a test.
- How long GitHub keeps its record of pushes is not documented. That is why the receipt time is copied into the
  log the next day and why the independent timestamp exists.
- The first sessions of the pilot test all of this on a separate pilot log (spec, section 7).

## Revisit
Revisit: by 2027-02, or before the owner's go for the start of the funds: check that the ruleset is on with nobody
exempt, that GitHub's record of pushes can still be read without an account, and that a stored timestamp can be
verified from a fresh copy of the repository.

## Sources
Read on 2026-11-17.
- Crosby and Wallach, [Efficient Data Structures for Tamper-Evident Logging](https://www.usenix.org/legacy/event/sec09/tech/full_papers/crosby.pdf) (USENIX Security 2009): "Tamper-evidence requires auditing"
- Russ Cox, [Transparent Logs for Skeptical Clients](https://research.swtch.com/tlog)
- [RFC 6962, Certificate Transparency](https://www.rfc-editor.org/rfc/rfc6962); [RFC 8785, JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785)
- Git: [line-ending conversion](https://git-scm.com/docs/gitattributes); [commit dates are set by the sender](https://git-scm.com/docs/git-commit-tree)
- GitHub documentation: [rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets),
  [repository activity](https://docs.github.com/en/rest/repos/repos#list-repository-activities),
  [events](https://docs.github.com/en/rest/activity/events)
- [GH Archive](https://www.gharchive.org/)
- [OpenTimestamps](https://opentimestamps.org), [client](https://github.com/opentimestamps/opentimestamps-client) (LGPL 3.0)
- [FreeTSA](https://freetsa.org/index_en.php); Sigstore's signing service [Fulcio](https://docs.sigstore.dev/certificate_authority/overview/) (records the signer's identity)
- The same chain already built for the archive: `docs/decisions/0001-day-1-archive-storage-and-backup.md`

Not verified: how long GitHub keeps its record of pushes and whether it stays readable without an account; who
runs the OpenTimestamps servers; how precise a Bitcoin block's time is (believed: within about two hours).
