# 0001. Day-1 archive: what is saved, where, in what form, and how it is backed up
Date: 2026-11-16
Status: accepted (the owner asked on 2026-11-16 to start the archive before the spec; the details below were chosen by
Claude and are open to change in the spec interview)

## Context
Several public sources overwrite their own past: the trial registry's data service gives only today's version of a record,
and exchange lists, fund holdings and regulator files are replaced daily (research: `docs/research/DATA-SOURCES.md`,
sections 2.1 and 13). The project may only test its agents forward in time, so it needs to know later what was public on
which day. Every day without a copy is history that cannot be recovered. So the archive starts now, before the spec.

What had to be decided, and would be costly to change after months of collecting:
- **the form** of the stored data (it must stay readable for years and provably unchanged);
- **the place** (not in the public repository; safe from accidents);
- **the backup** (this data is irreplaceable, and the laptop must hold nothing irreplaceable);
- **which sources** may be downloaded automatically at all.

Requirements:
- Save exactly what the source sent, with the time we fetched it. No analysis, no cleaning.
- Never change or delete a saved file. Be able to prove that later.
- Respect the sources' terms (owner, 2026-11-16: "we should respect the sources"). Raw data never goes into the public
  repository.
- Never send the owner's name, e-mail address or the project name with a request.
- Small and boring: standard library only, one daily job, an alert when it fails.
- Backup space is limited and shared with everything else the owner backs up.

## Options considered

**Form of the archive**

| Option | How it works | For | Against |
|---|---|---|---|
| **A. Plain files plus a checksum list** | Each download becomes one file in a dated folder. A text file (`manifest.jsonl`) gets one line per file with its fingerprint (SHA-256), address and time. | Readable with any tool, also in 20 years. Easy to back up. This is the idea behind BagIt, the standard that libraries use for file archives. | We write about 300 lines ourselves. |
| B. WARC files | The web-archiving standard (used by the Internet Archive): requests and responses packed into large container files. | A real standard; records the full exchange; has "seen before, unchanged" records. | Needs an extra library and special tools to look inside. Made for crawling web pages, more than we need for a dozen data files. |
| C. A database (SQLite or DuckDB) | Downloads stored as rows. | Easy to query. | One large file that changes daily: a bug or a crash can damage everything at once, and the nightly backup must upload the whole file again. Mixes "raw evidence" with "working data". |

**Place**

| Option | For | Against |
|---|---|---|
| **`~/bobby-hedgefund-data/`, outside the repository** | Same pattern as the other projects on this machine. Cannot be committed by accident. Survives deleting or re-cloning the repository. | One more folder in the home directory. |
| `data/` inside the repository (ignored by git) | Everything in one place. | A routine clean-up command (`git clean`) or deleting the folder would erase irreplaceable data. |

**Backup**

| Option | For | Against |
|---|---|---|
| **The machine's existing nightly encrypted backup** (restic, to cloud storage) | Already running, encrypted, monitored, with a phone alert on failure. Keeps older versions, so even a bug that damages the archive can be undone. Needs no change at all: the folder is inside the home directory. | The copy is encrypted, so it cannot be browsed in the cloud storage; restoring needs restic. |
| A separate `rclone` copy to a plain cloud folder | Files visible there. | A second backup system to build and watch. No older versions. Plain files in the cloud are not encrypted. |

## Decision
**Form: option A.** Plain files plus a checksum list, with three additions:
1. **Each line of the list contains the fingerprint of the line before it.** Changing or removing an older line breaks
   the chain, and `bobby-archive verify` reports it. This is the same idea the project plans for the agents' decision
   log. A chain cannot show by itself that its *newest* lines were cut off, so after every run the newest fingerprint
   and the line count are noted in a small side file (`manifest.head`) that `verify` compares with the list.
2. **A download identical to the previous one is not stored twice.** The list gets an "unchanged" line that points to the
   existing file.
3. **Large text files are compressed** (xz, lossless; the fingerprint is that of the original bytes). Trial-registry pages
   shrink about nine times.

Layout:
```
~/bobby-hedgefund-data/archive/
  manifest.jsonl                                  one line per stored file, per "unchanged" note and per run
  raw/<source>/<year>/<month>/<day>/<time>Z_<name>   times in UTC
```

**Place:** `~/bobby-hedgefund-data/`, outside the repository, readable by the owner only.

**Backup:** the machine's existing nightly encrypted backup. Nothing was changed in `~/server`.

**Schedule:** a systemd user timer at 23:30 (unit files in `systemd/`), with a phone alert when a source fails.

**Which code runs at night:** an installed snapshot of the program (`uv tool install`, made by `systemd/install.sh`),
not the project folder. Work in progress in the project folder, or another branch being checked out, can therefore
never run against the real archive. After a change is merged, `systemd/install.sh` is run again; it refuses to install
uncommitted code or code whose tests fail.

**Sources in the first version** (terms checked 2026-11-16):

| Source | What | Why it is allowed |
|---|---|---|
| ClinicalTrials.gov data service | Each working day: every trial record with a company as sponsor or collaborator whose update was posted since the last good run. Once: a full copy of those records (about 170,000) as the "before". | A public service built for programs, documented by the registry. Its `robots.txt` asks for one second between requests; we wait two. Its terms page could not be read by our tools: **unverified**. |
| European Medicines Agency files | Five files: medicines, post-authorisation procedures, orphan designations, referrals, paediatric plans. | EMA states the files "specifically target use via automated systems". Reuse with credit is allowed. EMA's site is strict about request speed (it refused the fourth file at 20 seconds apart), so we wait five minutes between files, and a refused file gets one more try at the end of the run. Even so, one of the five files was refused on each of the first two runs (a different one each time): **expect occasional EMA alerts** until the pattern is understood. |
| Nasdaq symbol directory | Two lists of all US-listed symbols, including the flag for companies failing listing rules. | Nasdaq documents these files for download. No conditions are stated on that page; its copyright page was not read: **unverified**. |
| SPDR XBI holdings | The fund's daily holdings file. | **Grey zone, owner may switch it off.** State Street's terms allow copies "for your own personal use" and forbid passing the data on. Nothing in the terms or in `robots.txt` forbids fetching this file by script. We fetch it once a day and never publish it. |

**Left out, and why:**

| Source | Reason |
|---|---|
| ARKG holdings (ARK) | ARK's `robots.txt` forbids all automated access to the site that holds the file. Alternatives for the spec: ARK's own free e-mail of daily trades (a sign-up by the owner) or the fund's monthly filings at the SEC. |
| Nasdaq non-compliant company list | The page is built in the browser and gave no data to a simple request; Nasdaq's terms page did not load. The symbol directory's status flag covers the main point. |
| Interactive Brokers borrow file | The public file server refused the connection on test day, and no reuse terms were found. |
| Prices, option prices | Need an account (owner creates it) and a choice of provider in the spec. |
| SEC filings | Need the contact e-mail in every request. Filings are permanent, so nothing is lost by waiting. |
| Company pipeline pages, investor presentations | Need the list of companies first, and a terms check per site. |
| Trials without any company involved | Left out to save space. A record that is skipped today can still be looked up by hand in the registry's own history view. |

## Consequences
- From 2026-11-16 the project has its own dated history of these sources.
- Size: the full registry copy took 444 MB (170,083 records, done 2026-11-16). After that roughly 1.5 GB a year
  (estimate from one day; the nightly backup uploads each file once).
- The raw pages of the trial registry overlap by a day or two between runs, on purpose: missing a record is worse than
  storing it twice. Later code that compares records must expect duplicates.
- Comparing versions, linking trials to companies and everything else that reads the archive is future work; the
  archive only saves.
- A change to the archive code only takes effect after `systemd/install.sh` is run again. Forgetting that means the old
  version keeps running, which is the safe side.
- A file is checked before it counts as saved: the right start, a minimum size, and a complete ending (valid JSON, a
  spreadsheet that opens, the closing line of the Nasdaq lists). A file that fails is still kept, flagged "suspect",
  and the alert fires.
- If the list is shorter than the side note says, or its noted line has changed, every writing command stops with
  an error until someone has looked (`bobby-archive verify` still works). Restoring an older copy of the list from
  the backup therefore needs a deliberate step: also restore or remove `manifest.head`.
- If another archive command is busy at 23:30, the nightly run waits up to two hours and then fails with an alert.
- There is no "the run did not start at all" alarm yet (only "a run failed"). `bobby-archive status` shows the last good
  run per source.
- If the laptop is off for more than a day, the overwritten files of those days are lost (the trial registry catches up
  by itself, the daily files cannot).
- The fingerprint chain proves that our files and list still match each other. It does not prove to an outsider *when* a
  file was saved; that needs the newest fingerprint to be published somewhere public every day (see below).

## Revisit
Revisit: by 2027-05, or when the archive passes 5 GB, the backup space runs short, or a source changes its
address or its terms of use.

Not part of the must-check, ideas for the spec: publish the daily chain fingerprint in the public repository (a public
timestamp); a Home Assistant "no archive run in 36 hours" alarm; store only changed trial records to remove the overlap.

## Verify
Checked on 2026-11-16: 76 automated tests, live runs (after which `bobby-archive verify` re-read all 182 stored files
and found no problem), and an independent review by a second agent that found 11
problems (among them: one failing file stopped the rest of its group; a full disk could damage the list; the newest
lines of the list were not protected). All were fixed and each has a test.
A second review, of those fixes, found one more serious problem: a run did not compare the list with the side note
before writing, so a list that had lost its newest lines would have been continued and the note replaced. Fixed: a
run now refuses to write in that case and the alert fires. Its smaller findings were fixed too (more kinds of damaged
files are flagged instead of stopping a group; new folders are synced to disk; the job's time limit is now 7 hours).
Left as is: `systemd/install.sh` installs whatever committed branch is checked out, so run it from `main`.

## Update 2026-11-16: terms that were marked "unverified" above
- **ClinicalTrials.gov** ([terms](https://clinicaltrials.gov/about-site/terms-conditions)): the data are free for all
  requesters. Conditions: credit ClinicalTrials.gov as the source, clearly show the date the data were processed, and
  (in the versions we could read) keep the data current and state any changes made to them. Some records may contain
  material under someone else's copyright. The terms hold for as long as we keep the data. NLM asks for the phrase
  "Source: National Library of Medicine" ([NLM web policies](https://www.nlm.nih.gov/web_policies.html)).
  **How it was read:** the live page only loads in a browser; this came from a search engine's copy of that page
  (several years old) and older archived versions. Nothing was found on request speed beyond `robots.txt`.
  **Confirmed 2026-11-17:** the owner opened the live page in a browser. The four conditions apply to "any
  publication or distribution of these data": attribute the source as ClinicalTrials.gov; keep the data current at
  all times; clearly display the date the data were processed by ClinicalTrials.gov; state any modifications, with
  a complete description. Also: claim no ownership of any part of the database and never present it as anything
  other than a United States Government database; do not use e-mail addresses from the records for marketing or
  promotion; the data carry an international copyright outside the United States, and some may be under the
  copyright of third parties; no warranty is given.
  **What this means for us:** we do not publish or pass on the records themselves. A published decision or report
  that uses a trial fact names ClinicalTrials.gov and the date of the record it was taken from, and says that the
  wording is our own summary. If the project ever publishes records themselves, all four conditions apply in full,
  including keeping them current: decide that in a new decision record first.
- **Nasdaq Trader** ([copyright and disclaimer](https://www.nasdaqtrader.com/Trader.aspx?id=CopyDisclaimMain), read
  in full): content may not be copied, stored or distributed without Nasdaq's written consent, except fair use and
  "one unaltered permanent copy to be used by the viewer for personal and non-commercial use only"; "Nasdaq stock
  symbols are proprietary to Nasdaq, Inc." Nothing is said about scripts. The site has no `robots.txt`.
  **Consequence: a grey zone, the same as the XBI file.** We keep a dated copy per day for personal, non-commercial
  use and never publish or pass on the files. The owner may switch this source off.
- **AACT** (not yet downloaded): its site shows no terms page. Its publisher asks to be credited as "Clinical Trials
  Transformation Initiative" with a link ([citation policy](https://ctti-clinicaltrials.org/?p=7671)), and the data
  come from ClinicalTrials.gov, whose terms then apply too. Ask AACT before building an automated download.
- Published results name the source and the date of the data wherever a source is used (README, "Data sources and
  credit").

## Sources
- BagIt, the file-archive format with checksum lists: [RFC 8493](https://www.rfc-editor.org/rfc/rfc8493)
- WARC 1.1, the web-archive format: [IIPC specification](https://iipc.github.io/warc-specifications/specifications/warc-format/warc-1.1/)
- "Raw data is immutable": [Cookiecutter Data Science, opinions](https://cookiecutter-data-science.drivendata.org/opinions/)
- restic backups: [documentation](https://restic.readthedocs.io/en/stable/040_backup.html); this machine's own backup setup is documented outside this repository
- What `robots.txt` means: [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309)
- ClinicalTrials.gov: [data service documentation](https://clinicaltrials.gov/data-api/api), [robots.txt](https://clinicaltrials.gov/robots.txt)
- EMA: [data files](https://www.ema.europa.eu/en/about-us/about-website/download-website-data-json-data-format), [legal notice](https://www.ema.europa.eu/en/about-us/about-website/legal-notice)
- Nasdaq: [symbol directory definitions](https://www.nasdaqtrader.com/Trader.aspx?id=SymbolDirDefs)
- State Street: [terms and conditions](https://www.ssga.com/us/en/intermediary/footer/terms-and-conditions), [robots.txt](https://www.ssga.com/robots.txt)
- ARK: [robots.txt](https://assets.ark-funds.com/robots.txt)
