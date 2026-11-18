# 0008. SEC filings: access rules, the contact address, and how filings are fetched
Date: 2026-11-17
Status: accepted (owner, 2026-11-17: read the main points and said "merge")

## Context
Stream 2 of the spec (`docs/SPEC.md`, section 6) saves the SEC filings of the 150-250 companies in the universe:
event reports, share sales, insider trades and filings by holders of more than 5% (the SEC's form names for these
are 8-K; S-3 and 424B5; Form 4; 13D and 13G). The
universe itself (record 0006) also rests on SEC data. Fetching is done by a nightly timer job without any model, like
the day-1 archive (`docs/decisions/0001`).

What had to be decided:
- **which rules of the SEC we follow**, read from the SEC's own pages before any download;
- **where the contact address lives** that the SEC wants in every request;
- **what does the fetching**: the spec names the edgartools library.

Requirements, from the project rules: follow the source's rules; requests carry a generic client name, never the
owner's name or the project name; the contact address comes from a local file that git ignores and is never printed,
logged or committed; saved files are exactly what the source sent and are never changed; every dependency's licence
is checked.

## Terms and robots.txt (read 2026-11-17)
Both pages were fetched from the SEC with a declared contact address, as the SEC asks.

**[Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)** says:
- "Anyone can access and download this information for free."
- "Current max request rate: 10 requests/second." And: "Download only what you need and please moderate requests to
  minimize server load."
- "Please declare your user agent in request headers", with the example
  `Sample Company Name AdminContact@<sample company domain>.com`.
- Requests from an automated tool "outside of the acceptable policy will be managed", meaning slowed down or blocked.
- The index files and the per-company folders under `/Archives/edgar/` carry files "to assist in automated crawling".
- Filings can be corrected or removed after acceptance. A copy saved on the day is therefore our own record of what
  was public then.

**[robots.txt](https://www.sec.gov/robots.txt)** allows `/Archives/edgar/data` and forbids `/cgi-bin`, among others.
The "latest filings" feed that the research listed (`docs/research/DATA-SOURCES.md`, "SEC EDGAR") lives under
`/cgi-bin` and is therefore **not used**. Full-text search is not used by scripts either: it is not documented as a
service for programs.

**Not read yet:** the `robots.txt` of `data.sec.gov`, the separate address of the SEC's documented data service.
It is read before the first request to that address, and the outcome is added here as an update.
(Done on 2026-11-18: see "Update 2026-11-18" below.)

**Reuse.** Filings are public and free to read and download. That is not the same as free to republish: the text of
a filing, and above all the press releases and slide decks attached to it, are written by the company. The public
track record therefore holds only our own summary with a link and at most a sentence or two of quotation
(`docs/SPEC.md`, section 5). This is our reading, not legal advice.

## Options considered

| Option | How it works | For | Against |
|---|---|---|---|
| A. Fetch with [edgartools](https://github.com/dgunning/edgartools) (MIT, open source) | The library downloads and reads filings in one step. | Ready-made readers for insider trades, holder filings and event reports. Sends the contact text unchanged; default speed 9 requests a second, can be set to 1. | Always keeps its own copy of what it downloads in a folder of its own, which cannot be switched off in the version read (6.2.0): a second store next to the archive, without fingerprints. Does not hand over the file exactly as received. Brings 37 other packages. Very fast-moving: 117 releases in 2026 and two breaking versions in a year, almost all by one maintainer. Has functions that use the forbidden `/cgi-bin` path and one that sends the contact text to another website (company logos); both only when called. |
| B. Fetch with [sec-edgar-downloader](https://github.com/jadchaar/sec-edgar-downloader) (MIT, open source) | A small library that only downloads. | Simple; saves the file as received. | Speed fixed at 10 requests a second, the SEC's maximum. Does not know the current names of the large-holder forms. Does not repair a file that was cut off by a crash. |
| **C. A small fetcher of our own; edgartools only reads files that are already saved** | Our own code asks the SEC's documented data service for each company's list of filings, downloads each new filing as one file, and stores it with the existing archive code. A separate step reads the saved files. | The file on disk is exactly what the SEC sent, in the fingerprint chain of record 0001. We set the speed and the header ourselves; only allowed paths are used. No new dependency for fetching. The reading step can be redone later with a better reader, because the raw file is kept. | About 150 lines of our own code to keep up. The ready-made readers arrive one step later. |

Checked by reading the source of both libraries (versions 6.2.0 and 5.1.0), without installing them.

## Decision
**Option C.**

1. **Fetching** is our own code, standard library only, built on the archive code of record 0001:
   - once per company per night: the company's filing list from the SEC's data service
     (`data.sec.gov/submissions/`);
   - once per new filing of a form type we follow: the complete filing as one text file from
     `/Archives/edgar/data/`. That one file holds all documents of the filing.
   - For 250 companies this is about 250 to 300 requests a night.
   - The monthly universe run (record 0006) needs more, once a month: the SEC's ticker file, and the filing list
     and reported share count of every company with the two industry codes, a few thousand requests in all. At one
     a second that is about an hour, run at night.
2. **Speed: at most one request a second**, a tenth of what the SEC allows. No parallel requests. When the SEC
   answers "too many requests" or refuses, the job stops for that night and sends the usual phone message.
3. **The header** is a generic client name followed by the contact address, in the SEC's own example form. It does
   not name the project, and it says nothing about the owner beyond what the address itself shows (the owner chose
   their normal address for this, see point 4).
4. **The contact address** is read from the local settings file that git ignores (`.env`, name
   `SEC_CONTACT_EMAIL`; `.env.example` holds the name only). The owner decided on 2026-11-16 that their normal
   address is used. The address is never written to a log, a saved file, an error message or the repository. If it
   is missing, the job does not run: it never sends a request without it or with a made-up one.
5. **Storage** follows record 0001: files exactly as received under `~/bobby-hedgefund-data/archive/raw/sec/`, one
   line per file in the fingerprint list, an unchanged filing list not stored twice.
6. **Reading** the saved files (which items an event report has, the lines of an insider trade) is a separate step.
   edgartools is the first candidate for it, used only on files already on disk and with its own downloading left
   unused. Whether it can do that without any network contact for every form type is tested when that step is
   built; if not, we read the few forms we need ourselves.
7. **Not used:** anything under `/cgi-bin`, full-text search, and bulk downloads of everything.
8. **Weekly cross-check:** the SEC's daily index files list every filing of a day. Comparing them with what we
   saved shows missed filings. One extra request per day checked.

## Differs from the spec
The spec says stream 2 is built "with the edgartools library". This record reads that as: **fetch ourselves, read
with edgartools**. Reason: fetching with it leaves a second, unprotected copy of the data outside the archive and
does not keep the file as received, which is the core rule of record 0001. The outcome for the agents is the same.
If the owner agrees, the spec gets a line under "Changes".

## Consequences
- Every filing we use exists as an unchanged dated file with a fingerprint, so it can be shown later what a session
  could have read.
- A night's run takes about five minutes.
- A filing published late in the US evening is picked up the next night. Sessions start in the European morning or
  early afternoon, so in practice a session sees everything filed up to the last nightly run; the data cut-off of
  the session says so (record 0003).
- Filings by others about a company (insider trades, large holders) are expected to appear in that company's filing
  list. This is checked on the first runs; if not, the daily index is used for those forms.
- Parsing mistakes cannot damage the evidence: the raw file stays.
- More code of our own than with option A, and it needs tests for the SEC's refusal answers.
- `docs/research/DATA-SOURCES.md` still lists the "latest filings" feed; this record overrules it.

## Revisit
Revisit: by 2027-05, or when the SEC changes its request limit, its header rule or its robots.txt, or when a nightly
run is refused.

## Update 2026-11-18: the data service's robots file, and the first company fetch
**Robots files, read with the declared header before any other request.**
- `https://data.sec.gov/robots.txt` does not exist (the service answers "not found"). So nothing there is forbidden
  to scripts; the rules that count are the ones on the "Accessing EDGAR Data" page above.
- `https://www.sec.gov/robots.txt` was read again in full: it does not mention `/files/`, where the
  company-ticker-exchange file lives. `/Archives/edgar/data` is allowed and `/cgi-bin` forbidden, as before.

**The monthly universe run asks for more than point 1 estimated.** Point 1 said "a few thousand requests, about an
hour", for the companies with our industry codes. But a company's industry code is only written in its own
filing-list file, and the SEC's search by industry code lives under the forbidden `/cgi-bin`. So the first run
fetches the filing list of every company in the ticker file that has a stock-exchange listing: 6,051 companies on
2026-11-18 (of 10,400 lines; the rest trade outside an exchange or have no listing). At one request a second that
is about two and a half hours, once. Later monthly runs fetch new companies and the current candidates. This stays
far inside the SEC's limit of 10 requests a second, and no bulk download is used (point 7).

**How it is built** (`src/bobby_hedgefund/archive/sec.py`, command `bobby-archive sec-companies`):
- the header is `public-data-archiver` followed by the contact address; the address is read by
  `src/bobby_hedgefund/settings.py` from the environment or the local `.env`. Tests check that it reaches no
  stored file, manifest line or printed line when the SEC refuses, when the connection drops and when our own code
  fails, and that it is not shown when the fetcher itself is printed;
- the header only ever goes to `www.sec.gov` and `data.sec.gov`: a redirect to any other host is refused, because
  a redirect carries the header along;
- a pause of one second before every request; "too many requests" and "forbidden" end the job at once, and
  `--resume` continues the same batch later. While a batch is unfinished, a fresh one starts only with `--new`;
- every file is stored as received under the archive source `sec`, with the batch and the company number in its
  manifest line; a filing list that did not change since the last batch is not stored twice;
- a company the data service does not know, or one whose answer is not its filing list, gets a note in the
  manifest and the job goes on; ten such answers in a row stop it;
- the job is started by hand. It holds the archive's lock while it runs, and the nightly run at 23:30 needs that
  lock: the command sends no new request after 22:30 local time and does not start after that time. What is left
  is fetched the next day with `--resume`.

A reviewer agent read the code before the pull request; its findings (the redirect rule, the odd answer that could
block a batch, the evening stop, the `--new` rule) are worked in.

## Update 2026-11-18 (2): the nightly filings, the cross-check and the reading step
Commands: `bobby-archive sec-filings`, `bobby-archive sec-crosscheck`, `bobby-filings recent`; the nightly
`bobby-archive run` does the filings as its last job.

- **What is fetched** (point 1): per universe company its filing list, then every filing of a followed kind
  that is not stored yet, from **1 September 2026** on (so the first fetch stays a few thousand requests), as the
  complete text file `/Archives/edgar/data/<company>/<accession number>.txt`. Followed kinds: 8-K; S-3,
  S-3ASR, 424B5; 4; SC 13D, SC 13G and their new names SCHEDULE 13D, SCHEDULE 13G; 10-Q and 10-K (for stream 4);
  and the amendments of all of these.
- **Checked on real filings:** insider trades and large-holder filings *do* appear in the company's own filing
  list (the open question under "Consequences"), so the daily index is not needed for them.
- **Storage:** archive source `sec-filings`: the filings, and the nightly copies of the filing lists (kept apart
  from the monthly company files of source `sec`, which belong to batches of the whole market).
- **An accession number** becomes part of an address and a file name, so only the SEC's own form of it
  (10-2-6 plain digits) is accepted. An answer is stored only when it starts as a filing and names that number
  in its first line; anything else (a "please wait" page) is not stored and asked again, and ten such answers in
  a row stop the job.
- **"Not found"** for a filing the list names is asked again on later nights and left alone after three times.
  A filing larger than 300 MB is noted and not asked again. Neither blocks the filings after it.
- **Time.** In the nightly run the job stops asking after 90 minutes; what is left comes the next night. By
  hand it stops at 22:30 like the other SEC commands. A refusal stops it at once (point 2).
- **Cross-check (point 8):** `sec-crosscheck` reads the SEC's daily index in its pipe-separated layout
  (`master.<day>.idx`) for the last seven days, stores each index file, and names every followed filing of our
  companies that the index lists and the archive does not hold; it then ends as failed, so it is noticed.
  **The SEC answers "forbidden" for a day without an index**, the same answer as a refusal. So weekends and
  regular market holidays are not asked for, and a "forbidden" on any other day stops the check. Read on
  2026-11-18: `robots.txt` does not forbid `/Archives/edgar/daily-index`, and the "Accessing EDGAR Data" page
  describes the index files for automated use. The check is run by hand for now (weekly); a timer can follow.
- **Reading (point 6): our own small reader, not edgartools.** What the first steps need is in the filing's
  plain header (kind, dates, the items of an 8-K) and, for an insider trade, in one small XML document, read
  with defusedxml (open source, PSF licence; it refuses the XML tricks that make a parser read files or use up
  memory). edgartools was **not installed or tried**: it would add 37 packages for these two readers. It stays
  the candidate for stream 4 (reading the numbers in quarterly reports), where a ready-made reader earns its
  place; the test "without any network contact" of point 6 is done then. The raw file is kept, so a better reader
  can always be used later.
- **Review.** A reviewer agent read the code before the pull request. Worked in, among others: the nightly
  filing lists first went into source `sec` and would have broken the monthly company fetch from the first night;
  one filing that fails every time no longer blocks the queue; the time limit for the nightly job; the index
  layout (the first version read the fixed-width layout with a guessed column width).

## Sources
- SEC, [Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) (read 2026-11-17)
- SEC, [robots.txt](https://www.sec.gov/robots.txt) (read 2026-11-17)
- SEC, [EDGAR application programming interfaces](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) (the data service; from the earlier research, not fetched again)
- edgartools: [repository](https://github.com/dgunning/edgartools), [PyPI](https://pypi.org/project/edgartools/), [configuration](https://edgartools.readthedocs.io/en/latest/configuration/); source of version 6.2.0 read
- sec-edgar-downloader: [repository](https://github.com/jadchaar/sec-edgar-downloader), [PyPI](https://pypi.org/project/sec-edgar-downloader/); source of version 5.1.0 read
- Earlier research: `docs/research/DATA-SOURCES.md` ("SEC EDGAR"), `docs/research/OPEN-SOURCE.md` ("SEC filings")
- Archive design reused: `docs/decisions/0001-day-1-archive-storage-and-backup.md`
