# 0007. Price source: Massive only; what is saved and what may be published
Date: 2026-11-17
Status: accepted (owner, 2026-11-17: read the main points and said "merge"). Open point 1 is answered (no publication of anything computed from prices); open point 2 is confirmed.

## Context
Prices are needed for the universe filter, for booking paper trades at the opening price, for the daily value of
every fund and for the comparison with index funds (`docs/SPEC.md`, section 6 stream 1, sections 4 and 5). The spec
planned Tiingo as the main source and Massive (formerly Polygon) as a second source to cross-check, both on their
free plans (owner: free sources only), and left to this record what their terms allow: what may be saved, and
whether single prices and index values may be shown in the public track record. The spec asked for this before the
format of the decision log is fixed (record 0004).

Requirements: follow each source's terms; never publish a source's data when its terms forbid it; the repository is
public; saved raw files are normally never deleted (`docs/decisions/0001`).

Both services are **closed, commercial services**. There is no open or official free source of US daily prices whose
terms allow publication (searched again for this record; the nearest, the free files of the IEX exchange, hold only
that one exchange's trades and their terms could not be read).

## Terms and robots.txt (read 2026-11-17)

### Tiingo: [terms of use](https://www.tiingo.com/tos), last updated 5 November 2026
The free ("Starter") plan cannot be used for this project.

| What we planned | Allowed on the free plan? | The terms say |
|---|---|---|
| Save the prices every night | **No** | 1.6(a): "you may not write, save, archive, back up, or otherwise retain Tiingo Data in any persistent or durable storage" |
| Use it to check a second source | **No** | 1.6: not for "using Tiingo end-of-day data to validate another end-of-day dataset" |
| Publish how AI agents perform | **Not without a paid enterprise licence** | 1.7(d): a licence is needed "to test, evaluate, compare, or benchmark the performance of any AI or machine learning model or system" |
| Show prices | **No** | 7.3: "All data via the API is for internal consumption only" |

Exceptions exist only on plans from $250 a month. `robots.txt` of the website and of the data service forbids only
`/admin`; it does not matter here.

### Massive: [terms for individuals](https://massive.com/legal/individuals-terms-of-service) and [market data terms](https://massive.com/legal/market-data-terms-of-service), both last updated 3 November 2026

| What we want | Allowed? | The terms say |
|---|---|---|
| Use by a private person for a hobby | Yes | "Personal use includes your own research, analysis and investment activities, using any software, tools or methods you choose" |
| Save the data on our own machine | Yes, while the account exists | A licence "to access, download, store and use the Information" |
| Keep it after the account ends | **No** | "you must stop using it and delete it promptly, and in any event within thirty (30) days, including downloaded files, stored copies and caches" |
| Publish prices, also single ones ("filled at $12.34") | **No** | Not allowed to "share, redistribute, publish … Information, make it available to anyone else" |
| Keep and use our own results computed from prices | Yes, when prices cannot be worked back out of them | You may keep and use, "for your own personal purposes, your own analyses and other results that do not contain Information and cannot reasonably be used to recreate it or as a substitute for it" |
| **Publish** such results | **Unclear**: the terms speak of keeping and using, not of publishing. See open point 1 | Same clause |
| Copies in an automatic backup after the account ends | For at most 90 days, unused | "An automatic backup that you do not actively use may retain a copy until it is overwritten in your normal backup cycle, and in any event for no more than ninety (90) days after your license ends" |
| Publish an index fund's daily value or return | **No**, by our reading: its prices can be worked back out | Same clause |
| Let Claude read the data | Yes, on a condition | A tool may process the data "only on your behalf"; it "may not use the Information for its own purposes". Using the data to train a model is forbidden |
| Publish an index or a benchmark made from the data | Not without a separate licence | Not allowed to "create, calculate or publish an index, benchmark, or settlement or reference price" |

`robots.txt` of massive.com forbids nothing; the data service has no robots file. We only call the documented data
service with the owner's key.

**Free plan as documented:** five requests a minute; two years of history; prices after the end of the day, for all
US shares; one request returns the whole market for one day; a day's prices are available after midnight New York
time (06:00 in Amsterdam); unadjusted prices can be asked for; share splits are listed.

### IWDA
Neither service carries IWDA: both cover US listings only. The US-listed fund on the same index (MSCI World) is
URTH. The spec already provides for this.

## Options considered

| Option | For | Against |
|---|---|---|
| A. As in the spec: Tiingo saved nightly, Massive as cross-check | - | Forbidden by Tiingo's terms (saving, cross-checking, publishing results of AI agents) |
| **B. Massive only, free plan; publish nothing from which a price can be worked back** | Allowed. One request a day gives the whole market. Storing is allowed | One source, so no cross-check. Prices and index-fund figures stay private. Data must be deleted if the account ever ends |
| C. A paid plan with the right to show data | Prices and index comparisons could be public | Costs money every month (owner: free only); the terms of such a plan were not read |

## Decision
**Option B.**

1. **Massive is the only price source. Tiingo is not used**, not for prices, not as a check.
2. **What is saved.** Every morning one request: the whole US market for the last trading day, with prices as
   they were traded ("unadjusted": not recalculated afterwards for share splits), being the opening, highest,
   lowest and closing price and the volume, exactly as received. Plus the list of share splits. A timer job without
   any model, like the archive's.
   **Once, at the start: the history the free plan offers (two years), one request per trading day**, spread over
   a few hours to stay under five requests a minute. The universe needs 60 trading days of it (record 0006), the
   check of the trading costs a year (record 0005), the historical study as much as there is.
3. **When.** Early in the morning, Amsterdam time, after the prices are out. (The spec said "every night"; the
   service only has a day's prices from 06:00.)
4. **Where: a folder of its own**, `~/bobby-hedgefund-data/prices/`, with its own fingerprint list, **not** inside
   the day-1 archive. Reason: the archive's rule is "never deleted", and these files must be deleted within 30 days
   if the Massive account ever ends. This is the one exception to the never-delete rule; while the account exists
   nothing is deleted. **Everything that contains a price follows the same rule:**
   - the price files;
   - the private part of the decision log (record 0004) and the private values of the funds, the Dice funds and the
     index funds (record 0005);
   - the numbers in the private universe files (record 0006);
   - the session folders and the saved conversations of the sessions (spec, section 3), which hold what the agents
     read; and Claude Code's own records of those sessions on this machine, which it removes by itself after 30
     days by default (that setting must not be made longer);
   - older versions of all of these in the machine's backup, which must be gone within 90 days.

   A script `bobby-prices purge` does the deleting and writes down what it removed; the step for the backup is
   described with it. Fingerprints of deleted content stay in the public log; `bobby-log verify` then reports
   "content deleted under record 0007" instead of damage. This is tested once on a copy before the funds start.
5. **No second source.** Instead the job checks each day's file against the day before: a price change of more
   than half without a share split or a filing is flagged for a look, and share splits are checked against the
   company's SEC filing (record 0005).
6. **What is never published. This is the one list of content that comes from prices; the log seals exactly
   this** (record 0004). Other things that are never published have their own rules: which companies are in the
   XBI fund (record 0006), and keys, addresses and long quotes (spec, section 5).
   - a price of any share or index fund, and a chart of any single share or index fund;
   - share counts of a position, the amount of money of a trade, its trading cost, a fund's cash (with the size in
     percent, each of them gives a price or a fund value away);
   - a market value of a company, or a figure per share, in any written text;
   - the daily value or return of XBI, IBB or URTH;
   - the daily values of the 1,000 Dice funds (record 0005): prices can be worked back out of them;
   - (open point 1, answered no on 2026-11-17, so for good:) the value and return of each of our own funds, their place among the Dice
     funds, and any comparison with an index fund.
7. **What is published in any case:** every decision with its thesis and its size as a percentage of the fund; the
   rule by which it will be filled (the one sentence of record 0003, point 4), and
   afterwards the day on which it was filled; every forecast and its outcome; the scores of the forecasts. The
   written text of a thesis, a day page or a letter is checked by a script for prices and numbers computed from
   them before it is published; what it finds is sealed (record 0004). Until that check exists, nothing is
   published.
8. **Agents may read prices.** The files stay on this machine and are read by the Claude session on the owner's
   behalf. Condition, see open point 2.
9. **IWDA** is replaced by URTH, as the spec provides; the track record says so.

## Open points for the owner
1. **May the funds' own results be public?** The value and return of each of our paper funds, their rank among the
   random funds, and a coarse comparison with the index funds (for example one figure per month) are our own
   results. By our reading they do not allow a price to be worked back, if position sizes are shown in percent and
   fund values are rounded. But the terms only say such results may be kept and used "for your own personal
   purposes"; they do not say "published". **Recommended:** the owner asks Massive in writing (a short question;
   Claude drafts it), before the funds start. If the answer is yes: the last item of the list in point 6 falls
   away, so our own funds' values (`values.csv`, our own funds only), their places among the Dice funds and the
   coarse comparison with the index funds are published. Everything else on that list stays unpublished whatever
   the answer. If it is no, or there is no answer by the owner's go: the owner chooses between keeping all figures
   computed from prices on the home network only (the public track record then shows decisions, theses and forecast
   scores, which is result 2 of the spec in full), and a paid plan. Until then nothing computed from prices is
   published.
   **Update 2026-11-17: the owner sent the question to Massive's support address.** It asks less than the text
   above: each fund's return in percent, rounded to one decimal, at most once a week; each fund's place among the
   random funds; and, as a part that may be refused separately, one sentence a month comparing a fund with an index
   fund. It states that AI models read the data on the owner's behalf with training switched off, and offers a
   credit line.
   **Answer from Massive's support, received 2026-11-17: no.** In short: the published terms are the whole
   agreement and support gives no separate permissions; personal, non-business use is allowed; and "any public
   display of our data/derived data requires a business license". **Outcome: nothing computed from prices is
   published**, also not rounded or weekly: no fund values, no returns, no place among the Dice funds, no
   comparison with an index fund. The last item of the list in point 6 therefore stays for good, and `values.csv`
   is not part of the public track record. All of it is kept in full on the owner's machine and shown in the app
   at home. A business licence is a paid plan; the owner's rule is free sources only, so it comes back only at a
   monthly review, with a concrete reason and a price.
2. **The Claude account must not use conversations for training.** Massive's terms forbid that a tool uses the
   data for its own purposes. The owner checks once that the setting that lets conversations be used to improve the
   models is off, and again at each monthly review.
   **Confirmed by the owner on 2026-11-17: the setting is off.** (Conversations still pass through Anthropic's
   service to be answered; the setting is about whether they are used to train models.)

## Differs from the spec
- Section 6, stream 1: Tiingo is dropped; no cross-check source; the download runs in the morning.
- Section 5: fill prices are not shown in the public log, and `values.csv` is not published at all
  (open point 1). The spec foresaw the first ("if not, the public log shows returns only"); the second is new.
- Section 5, the thesis: its numbers that come from prices (market value against cash, what the price seems to
  assume) are sealed in the public version.
- Section 3: the saved conversations of the sessions fall under the deletion rule.
- Section 4, "Index funds for comparison": the index funds are computed and shown privately (in the app on the
  home network), never publicly (open point 1).
- Rule "archived files are never deleted": one exception, point 4 above.
- The historical study has at most two years of prices from this source.

## Consequences
- The core promise is untouched: every decision is public before its price exists. Anyone can look up that price
  themselves; we just do not print it.
- The public track record holds no performance figures: it shows every decision with its reasoning, the day it
  was filled (with a link to a public page where the price can be seen), and every forecast with its score. Result
  1 of the spec (differences between funds) is worked out and kept privately; result 2 (quality of the
  probabilities) is fully public.
- The app on the home network can show everything: that is personal use.
- One source means a wrong price is harder to notice. The jump check and the filings catch the large mistakes.
- If Massive ends its free plan or changes its terms, the experiment has no prices. Saved files cover the past only
  while the account exists.
- After a deletion, the private half of the evidence is gone: it can still be shown that the public log was never
  changed, but no longer what the sealed numbers were, why a company passed the universe filter, or what exactly a
  session read.
- The Tiingo account is not needed any more. The owner may close it; its key stays unused.
- The whole-market file also covers companies outside the universe, which the monthly universe run needs
  (record 0006).

## Revisit
Revisit: by 2027-02, or when Massive changes its terms or its free plan, or before the owner's go for the start
of the funds, whichever comes first.

## Update 2026-11-18: how the download is built
Command `bobby-prices` (`src/bobby_hedgefund/prices/`). The service's documentation and four test requests were
read first; what they showed is written here because the pages do not say all of it.

- **Addresses used**, both on `api.massive.com`: the daily market summary
  (`/v2/aggs/grouped/locale/us/market/stocks/<day>?adjusted=false`) and the split list (`/stocks/v1/splits`,
  from two years back, in pages). Nothing else is asked.
- **The key travels in a request header**, never in an address: addresses are stored in the fingerprint list and
  printed in messages, headers are not. The fetcher only ever asks that one host, only over an encrypted
  connection, also after a redirect, and the address of a next page that would carry a key is refused. Tests check that the key reaches no stored file, no
  list line and no printed line, also when the service refuses, and that it is not shown when the fetcher is printed.
- **Speed:** a pause of 13 seconds before every request (under five a minute). "Too many requests" ends the job
  at once; running it again continues, because a day that is stored is never fetched twice.
- **What is stored:** the answer exactly as received, one file per trading day, compressed, in
  `~/bobby-hedgefund-data/prices/` with its own fingerprint list and lock (the archive's storage code, pointed at
  another folder). An answer is checked before it is stored: it must be marked as not recalculated for splits, its
  count must match, and every line must belong to the day asked for. Anything else is refused and not stored.
- **Days without prices.** A weekend is not asked for. The service answers a market holiday with an empty list,
  and it answers the same way for a day whose prices are not out yet, or when it has a hiccup. So an empty answer
  only counts as "the market was closed" when the day is more than four days old **and** either it is a regular
  US market holiday (worked out by rule in `prices/holidays.py`) or the service gave the same empty answer in two
  separate runs. `bobby-prices status` lists settled days that are not a regular holiday, for one look by a person
  (the market also closes on rare special days).
- **A day that looks half-filled.** A recent day with fewer than 80% of the usual number of shares (the middle
  value of the stored days within a month of it) is not stored but asked again on the next run; stored files are
  never replaced, so a half-filled file must not get in. After four days it is stored as it is, and marked.
- **A wrong answer for one day** (not the expected layout, prices of another day, "not found") is noted and the
  job goes on with the next day; the run then ends as failed, so the phone message goes out. A refusal ("too many
  requests", "forbidden") or a broken connection stops the job at once.
- **History.** The free plan refuses days older than two years ("past historical entitlements"). The one-time
  download starts 730 days back; a refusal within the oldest ten days of that is noted and not asked again, any
  other refusal is a failure. A day's file is about 1.4 MB as received and about 0.25 MB stored; about 520 days.
- **When.** A timer at 07:30 and again at 12:30 local time (point 3 said "early in the morning"): the second run
  costs nothing when the first got everything and catches prices that came out late. A failure sends the phone
  message "Bobby prices".
- **The split list** is asked from the first day of a month two years back, so the address stays the same for a
  month and an unchanged list is not stored again.
- **The check of point 5.** `bobby-prices check` compares each day with the stored day before and lists every
  closing price that moved by more than half without a share split between the two days. The morning run does this
  for each new day. The list covers the whole market, so it is long and mostly shows small shares; once the
  universe exists it is narrowed to it. The comparison with SEC filings comes with stream 2.
- **`bobby-prices purge`** (point 4) removes the whole prices folder, after writing a note that lists every
  removed file with its fingerprint (no prices). It needs an explicit flag, can only ever delete that one folder
  inside the data folder, and does not follow links. It takes the folder's lock (so it refuses while a download
  runs), sets the folder aside under another name in one step and only then deletes, so a download that starts
  meanwhile cannot write into what is being deleted; an interrupted purge is finished by running it again.
  Before a purge: switch the morning timer off and take the key out of `.env`. So far it covers the
  price files only; the other places that will hold prices (universe numbers, the private fund books, session
  folders) are added to it when they are built. The backup step stays a step by hand.
- **Review.** A reviewer agent read the code before the pull request. Worked in: one bad day no longer blocks
  the days after it; the half-filled-day rule; the two-answers rule for days without prices; encrypted addresses
  only; the purge keeps its lock while it sets the folder aside; days stored in a run that later fails are still
  compared.
- **Dividends** (listed under "Not verified"): not looked at; not needed before the fund books.

## Sources
All read on 2026-11-17.
- Tiingo: [terms of use](https://www.tiingo.com/tos) (sections 1.6, 1.7, 7.3), [pricing](https://www.tiingo.com/about/pricing), [robots.txt](https://www.tiingo.com/robots.txt)
- Massive: [terms for individuals](https://massive.com/legal/individuals-terms-of-service), [market data terms](https://massive.com/legal/market-data-terms-of-service), [pricing](https://massive.com/pricing), [robots.txt](https://massive.com/robots.txt)
- iShares, [URTH](https://www.ishares.com/us/products/239696/ishares-msci-world-etf) (tracks the MSCI World index)
- Earlier research: `docs/research/DATA-SOURCES.md` ("Prices"), now overtaken on Tiingo

Not verified: whether Massive counts coarse results as allowed (open point 1); whether the free plan lists
dividends; IWDA's index on its own page (taken from a search result); the terms of a paid plan.
