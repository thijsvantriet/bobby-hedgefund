# 0014. AACT: terms for downloading the dated registry copies
Date: 2026-11-17
Status: accepted (owner, 2026-11-17: "if they don't have it then they approve")

## Context
The historical study (`docs/SPEC.md`, section 6) needs the trial registry as it stood at past dates. AACT, run by
the Clinical Trials Transformation Initiative (CTTI), offers that: one full copy per month back to January 2017,
each about 2.6 GB, downloadable with the key of a free account (`docs/ACCOUNTS.md`).

The project rule is: before adding a download, read the source's terms of use and `robots.txt` and note the outcome
in a decision record. Record 0001 found no terms page and said "ask AACT before building an automated download".
This record settles that point. Nothing has been downloaded yet.

## Terms and robots.txt (read 2026-11-17)
- **[robots.txt](https://aact.ctti-clinicaltrials.org/robots.txt)** exists and holds only a comment line: it
  forbids nothing.
- **Terms of use:** none found. The home page, the page behind "how it works" and the sign-up page link to no terms,
  licence or privacy page, and the addresses `/terms` and `/privacy` do not exist. Pages behind the log-in were not
  read by a script.
- **What the service is for:** the key that every free account gets has one purpose, listing and downloading these
  copies (`docs/ACCOUNTS.md`). Downloading them with the key is the use the service is built for.
- **The publisher's [citation policy](https://ctti-clinicaltrials.org/?p=7671):** CTTI's materials "are available
  to the public for free"; it asks to be acknowledged as the "Clinical Trials Transformation Initiative", with a
  link, "whenever using or referencing our materials in any format". The policy is written for the materials on
  CTTI's own site; we apply it to AACT as well.
- **The data** come from ClinicalTrials.gov, whose terms the owner confirmed from the live page (record 0001,
  "Update"). They apply to the AACT copies too.

## Options considered

| Option | For | Against |
|---|---|---|
| A. Ask AACT in writing and wait | A written answer, as with the price service (0007). | Waits on a reply for a service that states no conditions and hands out a download key to every account. |
| **B. Go ahead under the rules we do know** | No waiting. Rests on what is written: an empty robots file, a key made for these downloads, a free-for-the-public policy, the registry's own terms. | No written yes. Missing terms are not a permission in the legal sense; this is the owner's reading, not legal advice. |
| C. Do without AACT | No open question. | No dated copies of the registry before our own archive started, so no historical study. |

## Decision
**Option B** (owner). No stated terms and an empty robots file are taken as permission to download with our key.

Rules for the download, so that it stays well within what a free account is given the key for:
1. Only monthly copies, only the ones the study's written rules ask for, each fetched once. One download at a time,
   at night, with a pause between copies. A refused or throttled request is not retried quickly.
2. The key comes from the local `.env`; requests carry a generic client name.
3. Copies are stored unchanged under `~/bobby-hedgefund-data/`, with a fingerprint each, and are never committed,
   published or passed on. Published results are our own numbers and conclusions.
4. Credit: "Clinical Trials Transformation Initiative" with a link, plus ClinicalTrials.gov, in the README
   ("Data sources and credit") from the first download on, and in every report that uses the data.
5. Stop and ask: if AACT publishes terms, limits the key, refuses requests, or says anything about automated
   use, the download stops and this record is revisited.

## Consequences
- The historical study is no longer blocked by a question to AACT.
- Space: all 116 monthly copies would take about 300 GB, more than the disk has free (about 150 GB on 2026-11-17).
  Which copies are fetched, and whether a copy is reduced to the tables the study needs after loading, is decided
  in the study's own rules before the first download.
- The risk that stays: AACT may later state conditions that differ from our reading. Then rule 5 applies.

## Revisit
Revisit: when the study's download is built (check the site again for terms on that day), when rule 5 is triggered,
or by 2027-05.

## Sources
- AACT: [home page](https://aact.ctti-clinicaltrials.org/), [robots.txt](https://aact.ctti-clinicaltrials.org/robots.txt), sign-up page (all read 2026-11-17)
- CTTI, [citation policy](https://ctti-clinicaltrials.org/?p=7671) (read 2026-11-17)
- How the key works: `docs/ACCOUNTS.md` ("AACT: how the key and the login work")
- Earlier finding: `docs/decisions/0001-day-1-archive-storage-and-backup.md` ("Update 2026-11-16")
