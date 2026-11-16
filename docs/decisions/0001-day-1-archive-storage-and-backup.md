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
- Google Drive has about 20 GB free (checked 2026-11-16), shared with everything else the owner keeps there.

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
| **The existing nightly home backup** (restic to Google Drive, 04:15; personal-data ADR 0009) | Already running, encrypted, monitored, with a phone alert on failure. Keeps older versions, so even a bug that damages the archive can be undone. Needs no change at all: the folder is inside the home directory. | The copy on Drive is encrypted, so it cannot be browsed there; restoring needs restic. |
| A separate `rclone` copy to a plain Drive folder | Files visible in Drive. | A second backup system to build and watch. No older versions. Plain files on Drive are not encrypted. |

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

**Backup:** the existing nightly home backup. Nothing was changed in `~/server`.

**Schedule:** a systemd user timer at 23:30 (unit files in `systemd/`), with a phone alert when a source fails.

**Which code runs at night:** an installed snapshot of the program (`uv tool install`, made by `systemd/install.sh`),
not the project folder. Work in progress in the project folder, or another branch being checked out, can therefore
never run against the real archive. After a change is merged, `systemd/install.sh` is run again; it refuses to install
uncommitted code or code whose tests fail.

**Sources in the first version** (terms checked 2026-11-16):

| Source | What | Why it is allowed |
|---|---|---|
| ClinicalTrials.gov data service | Each working day: every trial record with a company as sponsor or collaborator whose update was posted since the last good run. Once: a full copy of those records (about 170,000) as the "before". | A public service built for programs, documented by the registry. Its `robots.txt` asks for one second between requests; we wait two. Its terms page could not be read by our tools: **unverified**. |
| European Medicines Agency files | Five files: medicines, post-authorisation procedures, orphan designations, referrals, paediatric plans. | EMA states the files "specifically target use via automated systems". Reuse with credit is allowed. EMA limits request speed, so we wait 20 seconds between files. |
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
- Expected size: about 0.5 GB once for the full registry copy, then roughly 1.5 GB a year (estimate from the first
  runs; the nightly backup uploads each file once).
- The raw pages of the trial registry overlap by a day or two between runs, on purpose: missing a record is worse than
  storing it twice. Later code that compares records must expect duplicates.
- Comparing versions, linking trials to companies and everything else that reads the archive is future work; the
  archive only saves.
- A change to the archive code only takes effect after `systemd/install.sh` is run again. Forgetting that means the old
  version keeps running, which is the safe side.
- A file is checked before it counts as saved: the right start, a minimum size, and a complete ending (valid JSON, a
  spreadsheet that opens, the closing line of the Nasdaq lists). A file that fails is still kept, flagged "suspect",
  and the alert fires.
- If another archive command is busy at 23:30, the nightly run waits up to two hours and then fails with an alert.
- There is no "the run did not start at all" alarm yet (only "a run failed"). `bobby-archive status` shows the last good
  run per source.
- If the laptop is off for more than a day, the overwritten files of those days are lost (the trial registry catches up
  by itself, the daily files cannot).
- The fingerprint chain proves that our files and list still match each other. It does not prove to an outsider *when* a
  file was saved; that needs the newest fingerprint to be published somewhere public every day (see below).

## Revisit
Revisit: by 2027-05, or when the archive passes 5 GB, Google Drive has less than 10 GB free, or a source changes its
address or its terms of use.

Not part of the must-check, ideas for the spec: publish the daily chain fingerprint in the public repository (a public
timestamp); a Home Assistant "no archive run in 36 hours" alarm; store only changed trial records to remove the overlap.

## Verify
Checked on 2026-11-16: 70 automated tests, a live trial run, and an independent review by a second agent that found 11
problems (among them: one failing file stopped the rest of its group; a full disk could damage the list; the newest
lines of the list were not protected). All were fixed and each has a test. Details in the pull request that added this file.

## Sources
- BagIt, the file-archive format with checksum lists: [RFC 8493](https://www.rfc-editor.org/rfc/rfc8493)
- WARC 1.1, the web-archive format: [IIPC specification](https://iipc.github.io/warc-specifications/specifications/warc-format/warc-1.1/)
- "Raw data is immutable": [Cookiecutter Data Science, opinions](https://cookiecutter-data-science.drivendata.org/opinions/)
- restic backups: [documentation](https://restic.readthedocs.io/en/stable/040_backup.html); this machine's setup: `~/server/backup/README.md` and personal-data ADR 0009
- What `robots.txt` means: [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309)
- ClinicalTrials.gov: [data service documentation](https://clinicaltrials.gov/data-api/api), [robots.txt](https://clinicaltrials.gov/robots.txt)
- EMA: [data files](https://www.ema.europa.eu/en/about-us/about-website/download-website-data-json-data-format), [legal notice](https://www.ema.europa.eu/en/about-us/about-website/legal-notice)
- Nasdaq: [symbol directory definitions](https://www.nasdaqtrader.com/Trader.aspx?id=SymbolDirDefs)
- State Street: [terms and conditions](https://www.ssga.com/us/en/intermediary/footer/terms-and-conditions), [robots.txt](https://www.ssga.com/robots.txt)
- ARK: [robots.txt](https://assets.ark-funds.com/robots.txt)
