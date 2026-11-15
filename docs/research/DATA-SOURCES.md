# Data sources: the information streams for small and mid-size biotechs

Research night of 2026-11-15 (brief: [BRIEF.md](BRIEF.md)). Plain-language one-pager: [SUMMARY.md](SUMMARY.md).
Everything here is input for the spec session. Nothing is decided.

**How to read this**
- **[tested]** = a tiny anonymous test call worked on 2026-11-15 (log in section 12). **[checked]** = I re-checked the claim
  against the primary source. No tag = reported by a research agent with a link. **[unverified]** = no primary source found;
  check before relying on it.
- **Terms** answers two separate questions: may a script fetch it for personal use, and may we show it in a public repository.
- **History kept?** answers: does the source itself keep dated versions of what was known when, or does it overwrite, so that
  we must save our own copies from day 1.
- **Value** is for this fund: paper money, about 200 companies, at most one decision a day, six months.
- Policy and regulatory events from 2026 are reported from the linked sources and were not independently confirmed.
- Nothing here is legal advice.

## 1. The short version

1. **SEC filings are the backbone.** Free, official, public domain, and every filing carries a timestamp that never changes.
   Most of what moves a small biotech's price shows up there: results, share sales, insider trades, executive departures,
   delisting notices.
2. **The trial registry is the second pillar, with a catch.** ClinicalTrials.gov's API gives only the current version of each
   record. To see what changed (endpoint, size, dates, status) we must save a copy every day and compare.
3. **Save-it-yourself is the recurring theme.** Fund holdings, exchange lists, borrow fees, company pipeline pages and the
   trial registry all overwrite their past. Anything not saved from day 1 is gone. Section 13 has the list.
4. **The most valuable overlooked streams are not exotic.** They are the financing fine print, wording changes between
   consecutive filings, and the inspection record of the contract manufacturer behind a pending approval. Section 9.
5. **Social media is effectively closed.** X, Reddit and StockTwits now need payment or approval. Most "alternative data" is
   noise for this fund.
6. **Two things need the owner before any script runs:** a contact e-mail for the SEC (mandatory), and a rule that the public
   repository shows only our own computed results. Section 15.
7. **Evidence is thinner than the stories suggest.** For several attractive signals (registry edits, specialist-fund
   ownership, pipeline-page changes) no peer-reviewed study links them to returns. They are hypotheses our own experiment tests.

## 2. Three points that cut across every source

**2.1 Point in time.** The project rule is "no look-ahead". That needs, for every piece of data, the moment it became public
and the moment we fetched it. Sources fall into three groups:

| Group | Examples | What we do |
|---|---|---|
| Timestamped and never changed | SEC filings, Federal Register, preprint versions, EMA and Purple Book monthly files | Fetch when needed; history can be rebuilt later |
| History exists but not through an open API | ClinicalTrials.gov (website shows versions; API does not) | Save daily copies; treat the website history as a manual lookup |
| Overwritten | ETF holdings, Nasdaq lists, borrow fees, option prices, company web pages, vendor "adjusted" prices | Save daily copies from day 1 or lose it |

**2.2 Linking.** A trial record names a sponsor in free text, a filing names a company number, a price feed names a ticker, a
paper names a drug code. Nothing open connects them. See [OPEN-SOURCE.md](OPEN-SOURCE.md) section 7 for the building blocks.
Every stream below is only useful once this linking table exists.

**2.3 Volume, for the token budget** (rough estimates by the research agents; measure in the pilot week):

| Stream, for ~200 companies | Per business day | Size each |
|---|---|---|
| SEC filings in total | 60-100 | mostly insider-trade forms under 1k tokens |
| of which 8-K event filings | 10-15 | 2-10 pages plus exhibits |
| Quarterly and annual reports | bursts in reporting season | 30-60k tokens (quarterly), 100-150k (annual); send sections only |
| Press releases | 15-30 | 1-3k tokens |
| Trial record updates | 5-40 | about 17 KB of structured data; compare by script, interpret by agent |

## 3. Clinical trial registries

| Source | What | Access and cost | Terms | History kept? | Freshness | Effort | Value |
|---|---|---|---|---|---|---|---|
| **ClinicalTrials.gov API v2** | Status, enrolment, dates, endpoints, sites, results | [REST API](https://clinicaltrials.gov/data-api/api), no key, free **[tested]**; RSS also works | US government data; terms page could not be read by our tools **[unverified]**; attribution advisable | **Website yes, API no.** Internal history route returns 403 to scripts **[tested]** | Each weekday; changes appear days to weeks after the real event | Low | **High** |
| [AACT](https://aact.ctti-clinicaltrials.org/) | The same registry as a database | Free, **account required** | Licence terms not found | Dated snapshots | Daily | Medium | Medium (historical study) |
| EU CTIS | EU trials since 2023, some protocol documents | [Public portal](https://euclinicaltrials.eu/); no documented API | [EMA legal notice](https://www.ema.europa.eu/en/about-us/about-website/legal-notice): reuse with credit | Overwrites | Unknown | High | Low-medium |
| WHO ICTRP | Combines ~17 national registries | Search portal; automated service unavailable | **Research use only, no commercial use** ([conditions](https://www.who.int/tools/clinical-trials-registry-platform/network/who-data-set/downloading-records-from-the-ictrp-database)) | No | Weekly **[unverified]** | High | **Avoid** |
| China (ChiCTR, CDE), Japan (jRCT) | National registries | Web only, Chinese/Japanese | Not found | No | - | High | Low (only for assets licensed from China) |
| Australia (ANZCTR) | Many US small caps run cheap phase 1 trials here | Manual export, no API ([FAQ](https://anzctr.org.au/Faq.aspx)) | Not found | No | - | Medium-high | Low |
| Results postings | Summary results after completion | Fields in the API | - | - | Legally due within 12 months; often late or never ([report](https://www.thetransmitter.org/spectrum/sponsors-of-clinical-trials-may-report-data-late-or-never/)) | Low | Low-medium: press releases come first |

**What to watch in a trial record** (found by comparing our own daily copies):
- status changes, above all to *suspended*, *terminated* or *withdrawn*, with the "why stopped" text. FDA does not publish
  clinical holds, so this is one of the few places they surface;
- the primary completion date moving, and the switch from "estimated" to "actual" (data collection finished; results usually
  follow in weeks to months);
- the enrolment target being cut, or actual enrolment falling short;
- changes to the primary endpoint, arms, doses, sites and countries.

**Traps.** "Primary completion" is the last patient visit, not the readout date. Many records are stale. Sponsor names are
free text. A meta-research study found 23% of trials change their primary outcome
([PMC10645365](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10645365/)), so a change alone is not rare.

**Does it predict prices? Thin evidence.** Trial *outcomes* clearly move prices, most for small companies
([Singh et al., PLoS ONE 2022](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9439234/)). For registry *edits*, one
non-peer-reviewed preprint from October 2026 reports that cutting enrolment targets and changing primary outcomes predicted
later termination, while postponed completion dates (seen in 61% of trials) did not
([preprint](https://www.researchsquare.com/article/rs-11447828/latest), summary only). No peer-reviewed study links registry
edits to share returns. Treat it as a hypothesis for our experiment.

## 4. Regulatory sources

### United States (FDA and related)

| Source | What | Access and cost | Terms | History kept? | Freshness | Effort | Value |
|---|---|---|---|---|---|---|---|
| **openFDA** | Approvals and submissions, labels, recalls, shortages, Orange Book, adverse events | [api.fda.gov](https://open.fda.gov/apis/), free; no key: 1,000 calls/day; free key: 120,000 ([limits](https://open.fda.gov/apis/authentication/)) **[tested]** | **CC0**, no attribution needed ([licence](https://open.fda.gov/license/)) | Overwrites | Daily | Low | Medium: confirms approvals |
| openFDA gap | **Cell and gene therapies, vaccines (CBER) are missing**: Casgevy not found **[tested]** | Use FDA's CBER approval pages and "What's New: Biologics" feed | Public domain | No | Days | Medium | Medium: many small caps are cell or gene therapy |
| **Rejection letters (CRLs)** | Redacted letters, 458 in total | [openFDA endpoint](https://open.fda.gov/apis/transparency/completeresponseletters/) **[tested]** | CC0 | Static documents | **Stalled: last updated 2026-08-13** **[tested]**. Real-time release reportedly paused April 2026 ([report](https://www.appliedclinicaltrialsonline.com/view/fda-pauses-real-time-release-drug-rejection-letters-formalize-policy)) | Low | Medium: a library of why applications fail, and a check on what a company said about its own rejection |
| **FDA decision dates (PDUFA)** | **Not published by FDA** | Company filings and press releases; check against the review clock (below) | - | Our own versioned calendar | - | Medium | **High** |
| Advisory committees | Dates, briefing documents, votes | [Calendar](https://www.fda.gov/advisory-committees/advisory-committee-calendar) (empty on test day) and Federal Register notices at least 15 days ahead | Public domain | Notices are permanent | - | Medium | High when they happen, but rare now: 14 meetings in 2025 against 38 in 2024 ([report](https://www.center4research.org/stat-fda-shuns-advisory-committee-meetings/)) |
| **Federal Register API** | Meeting notices, rules, guidance, tariff and pricing actions | [API](https://www.federalregister.gov/developers/documentation/api/v1), no key, free **[tested]** | Public domain | **Yes, permanent and dated** | Daily | Low | Medium |
| FDA feeds and approval pages | Press releases, new approvals, novel-drug list | [Feed list](https://www.fda.gov/about-fda/contact-fda/subscribe-podcasts-and-news-feeds); [novel approvals](https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2026) | Public domain | No | Minutes to a day | Low | Medium |
| National priority vouchers | Review target of 1-2 months instead of 6-10 | [FDA announcement, Oct 2025](https://www.fda.gov/news-events/press-announcements/fda-awards-first-ever-national-priority-vouchers-nine-sponsors) | Public domain | - | Ad hoc | Low | High for the named companies: the catalyst comes much sooner |
| Warning letters | Letters to companies and manufacturers | [FDA page](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters), web | Public domain | Yes | Weekly **[unverified]** | Medium | Medium, see section 9.1 |
| Inspection results | Classifications, citations, import refusals | [Data Dashboard](https://datadashboard.fda.gov/oii/cd/inspections.htm) web download; the [API](https://datadashboard.fda.gov/oii/api/index.htm) needs a key issued against name and e-mail | Public domain **[unverified]** | Yes | Lags inspections by months | Medium | Medium, see section 9.1 |
| Clinical holds | **Not published** | Company filings; trial status "suspended" | - | - | Company's discretion | - | High, hard to get early |
| Orphan and other designations | Orphan database; others only via companies | [FDA database](https://www.accessdata.fda.gov/scripts/opdlisting/oopd/) | Public domain | No | Monthly | Medium | Low-medium: companies announce these themselves |
| Orange and Purple Book | Patents and exclusivity | openFDA; [Purple Book files](https://purplebooksearch.fda.gov/downloads) | Public domain | Purple Book: dated monthly files | Monthly | Low | Low within six months |
| Adverse events (FAERS) | Side-effect reports | openFDA | CC0 | Quarterly | Months late | Medium | Low: noisy and late |
| Medicare price negotiation, CMS spending | Selected drugs, spending per drug | [CMS](https://www.cms.gov/files/document/factsheet-medicare-negotiation-selected-drug-list-ipay-2028.pdf) | Public domain | Yearly | Annual | Low | Low: concerns big-pharma blockbusters |

### Outside the United States

| Source | What | Access | Terms | History kept? | Effort | Value |
|---|---|---|---|---|---|---|
| **EMA data files** | 18 files: medicines, orphan designations, referrals, meetings and more | [JSON downloads](https://www.ema.europa.eu/en/about-us/about-website/download-website-data-json-data-format), updated twice a day **[tested]** | Reuse allowed with credit, also commercially ([legal notice](https://www.ema.europa.eu/en/about-us/about-website/legal-notice)) | Overwrites | Low | Medium |
| EMA medicines under evaluation | Monthly list of drugs under review, with clock-stop restarts | [EMA page](https://www.ema.europa.eu/en/medicines/medicines-human-use-under-evaluation) | As above | Monthly files kept | Low | Medium: reveals EU filings never press-released |
| CHMP meeting highlights and agendas | Opinions; an "oral explanation" on the agenda often precedes a negative opinion **[unverified]** | EMA pages, PDF | As above | Dated | Medium | Medium for the few with an EU application |
| EU joint clinical assessments | Mandatory for new cancer drugs and advanced therapies since 2025 | [EC list](https://health.ec.europa.eu/latest-updates/updated-list-joint-clinical-assessments-2026-07-08_en) | EU reuse | - | Low | Low-medium |
| UK, Japan, China, Canada regulators | Approvals | Web; partly APIs | Mostly open government licences **[unverified]** | - | Medium-high | Low |
| ICER, NICE | Cost-effectiveness reviews | PDF; terms restrict reuse **[unverified]** | - | - | Medium | Low-medium |

### Recipe: our own catalyst calendar without a closed provider
1. **Dates from the companies.** Agents extract decision dates, filing acceptances and expected readouts from 8-K filings,
   press releases and quarterly reports, each with source link and timestamp.
2. **Check against the official review clock** ([PDUFA commitment letter](https://www.fda.gov/media/151712/download)):
   new drugs and biologics, standard review 10 months after the 60-day filing date, priority review 6 months; resubmission
   after a rejection 2 or 6 months; a major amendment adds 3 months (the classic "decision delayed" announcement).
3. **Advisory committees** from Federal Register notices.
4. **Expected readouts** from company guidance, cross-checked with the registry's completion date and conference dates.
5. **Every entry is versioned**: when first seen, from where, and each later change. A slipping date is itself a signal.

The closed calendars (BiopharmCatalyst, RTTNews at $99 a month, Benzinga and others) can be consulted by hand for
cross-checking; their terms generally forbid automated use.

### Changes at FDA that affect timing and data (2025-2026)
Staff cuts announced March 2025 ([NPR](https://www.npr.org/sections/shots-health-news/2025/03/27/nx-s1-5342414/hhs-doge-rif-rfk-job-cuts));
publication of rejection letters from July 2025, then paused; far fewer advisory committees; priority vouchers with 1-2 month
reviews; a government shutdown in autumn 2025 during which new fee-paying submissions were not accepted
([summary](https://www.jdsupra.com/legalnews/fda-operations-during-the-fy-2026-4823215/)); leadership changes in 2026 **[unverified
at primary source]**. Practical effect: decision dates are less predictable than the official clock suggests.

## 5. Company sources

### SEC EDGAR
| Channel | What | Notes |
|---|---|---|
| [Submissions API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | Filing list per company | Updated within about a second |
| Financial data API (XBRL) | Reported figures | Standard items only; small-company tagging is messy |
| Latest-filings feed | New filings as they arrive | Filings appear 1-3 minutes after acceptance |
| [Full-text search](https://www.sec.gov/edgar/search) | Search in all filings since 2001 | Not documented as an API; occasional lookups only |
| Nightly bulk files | Everything | For backfill |

**Rules: at most 10 requests a second, and every request must carry a User-Agent with a contact e-mail**
([SEC](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)). For that reason no test call was
made. Filings are US government publications and can be shown publicly; the press releases and slide decks attached to them
are company copyright, so quote briefly.

| Filing | What it tells a biotech investor | How fast | Value |
|---|---|---|---|
| **8-K** | Unscheduled events: deals (item 1.01), results (2.02), **delisting notice (3.01)**, **executive departures (5.02)**, charter changes such as reverse splits (5.03), presentations (7.01), trial results and FDA letters (8.01) | Most items within 4 business days; 7.01 and 8.01 are voluntary ([Investor.gov](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/how-read-8)) | **High** |
| **10-Q / 10-K** | Cash, burn, the "runway into…" sentence, going-concern doubt, risk factors, loan covenants | Quarterly / yearly | **High** |
| **S-3 shelf, 424B5 supplement** | Permission to sell shares, then the actual sale: price, size, warrants, at-the-market programmes | When filed; supplement within days of pricing | **High**: dilution as it happens |
| **Form 4** | Insider purchases and sales | 2 business days | **High** for open-market purchases, especially several insiders together; sales are mostly noise |
| Form 144 | Planned insider sale | Before the sale | Low-medium |
| **13D / 13G** | A holder crosses 5% | 5 business days; amendments 2 ([summary of the 2023 rule](https://www.foley.com/insights/publications/2023/10/sec-adopts-changes-schedule-13d-schedule-13g/)) | High-medium: far quicker than 13F |
| 13F | Quarterly long positions of large managers | **45 days after quarter end**; long US positions only, no shorts ([SEC FAQ](https://www.sec.gov/rules-regulations/staff-guidance/division-investment-management-frequently-asked-questions/frequently-asked-questions-about-form-13f)) | Medium as signal, high as benchmark |
| NT 10-K / NT 10-Q | Late filing notice | Event | Medium-high red flag, rare |
| Proxy (DEF 14A) | Votes on more authorised shares or a reverse split | Yearly | Medium: signals coming financing |
| 20-F / 6-K | Foreign issuers: annual report only, no quarterly duty, no insider forms **[unverified]** | Less frequent | Medium |
| Merger and tender filings | Takeovers | Event | High, but public knowledge by then |

A proposal from May 2026 would let companies report half-yearly instead of quarterly
([summary](https://www.venable.com/insights/publications/2026/05/sec-proposes-optional-semiannual-reporting-for)); not final
as far as found. Worth watching: it would halve our best regular source.

**Published evidence on filing signals**

| Signal | Evidence | Strength for small biotech |
|---|---|---|
| Insider purchases | Non-routine insider trades earn about 0.8% a month extra; routine ones nothing ([Cohen, Malloy, Pomorski 2012](https://www.nber.org/papers/w16454)) | Strong in general, thin for biotech. Exclude insiders merely taking part in a company financing |
| First going-concern warning | -14% drift over the following year ([Kausar, Taffler, Tan 2009](https://econpapers.repec.org/RePEc:bla:joares:v:47:y:2009:i:1:p:213-239)) | Moderate. About a third of listed life-science companies carry one ([RSM](https://rsmus.com/insights/services/audit/biotech-financing-structures-and-accounting-implications.html)), so it discriminates poorly; the *change* matters |
| Wording changes between reports | Companies that change their annual-report text underperform by about 1.9% a month, with no reaction on filing day ([Cohen, Malloy, Nguyen 2020](https://doi.org/10.1111/jofi.12885)) **[checked: link resolves]** | Strong in general; see section 9.2 |
| At-the-market share sales | Descriptive study only ([Billett et al. 2019](https://ideas.repec.org/a/cup/jfinqa/v54y2019i03p1263-1283_00.html)) | Thin |
| Specialist-fund ownership | Vendor back-tests only ([summary](https://larryswedroe.substack.com/p/cracking-the-code-a-quantitative)); no peer-reviewed study | Thin but consistent |

### Press releases, presentations, calls

| Source | Access | Terms | Value and effort |
|---|---|---|---|
| **Company investor-relations feeds** | RSS on most company sites | Company-owned, offered for subscription; varies per site | **High, low-medium effort**: the fastest allowed trigger. Collect ~200 feed addresses once |
| The same release as an 8-K exhibit | EDGAR | Public filing | The authoritative timestamped copy; usually same day, legally up to 4 business days later |
| PR Newswire | RSS exists | **Terms ban robots, scraping and AI training** ([terms](https://prnewswire.com/terms-of-use/)) | Avoid automating |
| GlobeNewswire | RSS exists | Terms ban bots; whether a feed reader counts is unclear ([terms](https://portal.notified.com/terms-conditions/en)) | Owner decision |
| Business Wire | RSS | Terms appear to allow "retrieving RSS feeds" ([terms](https://www.businesswire.com/terms-of-use), snippet only) | Usable with care |
| Investor presentations | Company sites (overwritten); often also an 8-K exhibit (permanent) | Company copyright | Medium: stated timelines and catalysts. Save copies |
| Earnings-call transcripts | Seeking Alpha, FactSet, AlphaSense and similar | **Closed, licensed** | Avoid |
| Own transcription of public webcasts | Download plus local speech-to-text | See below | Medium-high effort; owner decision |

**Transcribing public webcasts (not legal advice).** EU law allows text-and-data mining of lawfully accessible works unless
the rightholder has reserved that right in a machine-readable way ([Directive 2019/790, art. 4](https://eur-lex.europa.eu/eli/dir/2019/790/oj);
Dutch Auteurswet art. 15o, via secondary sources). In the US a court held that even distributing a full earnings call to
subscribers was fair use ([Swatch v. Bloomberg, 2014](https://www.copyright.gov/fair-use/summaries/swatchgrp-bloomberg-2dcir2014.pdf)).
Private download, local transcription and analysis, with nothing republished, looks low-risk; individual site terms can still
forbid it. Many small biotechs hold few calls, so the gain is modest.

**Fastest open route to material news:** company feed first, EDGAR as the record. Record the first-seen time on every channel;
the pilot week then measures the real delays.

## 6. Market data

### Prices
**No free source is at once legally clean, complete with delisted companies, and republishable.** **[tested]** Stooq, the
classic free source, now answers scripts with a browser check instead of data.

| Source | Free tier | Terms | Verdict |
|---|---|---|---|
| Tiingo | Key; about 1,000 calls a day, 500 tickers a month **[unverified exact limits]** ([docs](https://api.tiingo.com/documentation)) | Closed; personal use | Best free fit for ~200 tickers |
| Massive (formerly Polygon) | Key; 5 calls a minute, 2 years of history **[unverified]** ([pricing](https://massive.com/pricing)) | Closed; individual use | Good second source; also lists splits and ticker changes |
| Yahoo via yfinance | No key, unofficial | Closed; personal use only | Fragile cross-check |
| Alpha Vantage, EODHD, Twelve Data | 25 / 20 calls a day; non-display terms | Closed | Too limited |
| Alpaca | Needs a brokerage account, even for paper | Closed | Conflicts with "no broker" |
| Stooq, IEX Cloud | Blocked / shut down in 2024 | - | Avoid |

**Trap.** After every reverse split vendors rewrite their "adjusted" price history, so a series saved last month no longer
matches a fresh download. Save the raw close and volume every day and apply splits ourselves from our own table.
**IWDA** trades in Amsterdam and London in euros and dollars; one call a day from a free tier is enough; compare in one
currency and record the exchange-rate source.

### Corporate actions and the universe

| Source | What | Access | History kept? | Value |
|---|---|---|---|---|
| **Nasdaq symbol directory** | All listed symbols with a financial-status flag (deficient, delinquent, bankrupt) | [Text file](https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt), no key **[tested]** | **Overwritten daily** | High, trivial |
| **Nasdaq non-compliant list** | Companies failing listing rules, such as a share price under $1 | [Web page](https://listingcenter.nasdaqomx.com/NonCompliantCompanyList.aspx) | **Current state only** | High as a warning of reverse split or delisting |
| SEC 8-K items 3.01, 5.03, 2.01 and Form 25 | Delisting notices, reverse splits, completed mergers | EDGAR | Permanent | High |
| Nasdaq Daily List | Official corporate actions | About $3,500 a month ([filing](https://www.sec.gov/files/rules/sro/nasdaq/2026/34-106034.pdf)) | - | Avoid |
| **SPDR XBI holdings** | About 140 small and mid-size biotechs: the core universe | [Daily file](https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-xbi.xlsx) **[tested]**; terms on automated download **[unverified]** | **Overwritten daily** | High |
| iShares IBB holdings | Larger biotechs | Returned a web page, not the file **[tested]**; terms ban bots on at least one page ([terms](https://www.ishares.com/us/compliance/factor-box-terms)) | Overwritten | Medium; download by hand monthly |
| SEC industry codes 2834, 2836 | Every pharma and biotech filer, including delisted ones | EDGAR | Permanent | High: a list without survivorship bias |

Proposed universe: XBI holdings, Nasdaq Biotechnology Index members and SEC-coded filers, filtered on our own size and volume
floor, frozen with a date at the start and re-run monthly with every version kept. Shares outstanding from filings lag recent
share sales by up to a quarter.

### What is priced in: options, short interest, borrow cost

| Source | What | Access | Terms | History kept? | Value |
|---|---|---|---|---|---|
| Option prices via Yahoo | The "implied move" around a catalyst | yfinance, unofficial | Personal use; fragile | **None**: save daily | The only free route. Many small biotechs have thin or no options |
| Paid options data | Proper implied-volatility history | Roughly $30-100 a month **[unverified]** | Closed | Yes | Owner decision |
| **FINRA short interest** | Shares sold short, twice a month | [Files](https://www.finra.org/finra-data/browse-catalog/equity-short-interest), free | Personal non-commercial use, credit FINRA ([terms](https://developer.finra.org/sites/default/files/2022-12/Developer%20API%20-%20Specific%20Terms%20-%20Equity%20Data%20%2812-2022%29%5B10%5D.pdf)) | Yes | High for small biotech |
| FINRA daily short volume | Off-exchange short volume | [Files](https://cdn.finra.org/equity/regsho/daily/) **[tested]** | As above | Yes | Low: routinely misread as short interest |
| **Interactive Brokers borrow file** | Fee and shares available to borrow | Public FTP, no account ([IBKR](https://ibkb.interactivebrokers.com/article/2024)) | Reuse terms not found **[unverified]** | **Overwritten during the day** | Medium-high: borrow cost is the best free sign of a crowded short |
| SEC fails-to-deliver | Settlement failures | Twice monthly | Public | Yes | Low: noise |

A no-cost alternative to options for "what is priced in": compare the company's market value with its cash. A value near or
below cash means the market gives the pipeline almost nothing.

### Index changes, ETF holdings, fund holdings

| Source | What | Notes | Value |
|---|---|---|---|
| Russell index rebuild | Now twice a year. **First December rebuild takes effect after the close on 2026-12-11** ([LSEG](https://www.lseg.com/en/media-centre/press-releases/ftse-russell/2026/ftse-russell-announces-december-2026-russell-us-indexes-reconstitution-schedule)) | Inside our likely live window; a known source of forced buying and selling | Medium, as a calendar item |
| Nasdaq Biotechnology Index | Rebuilt each December ([method](https://indexes.nasdaqomx.com/docs/methodology_NBI.pdf)) | Announced early December | Medium |
| XBI's index | Rebalanced quarterly; no longer purely equal-weight since 2024 ([BioCentury](https://www.biocentury.com/article/652965/biotech-losing-its-xbi-barometer)) | Matters for the benchmark comparison | Medium |
| **ARKG daily holdings** | [CSV](https://assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_GENOMIC_REVOLUTION_ETF_ARKG_HOLDINGS.csv) **[tested]** | **ARK keeps no history of its trades** ([ARK](https://helpcenter.ark-funds.com/do-you-share-historical-trades)); save daily | Medium: benchmark, not signal |
| **SEC 13F data sets** | [Quarterly files](https://www.sec.gov/dera/data/form-13f) of all fund holdings | Public domain | High as benchmark, low as signal (45 days late) |

Specialist biotech funds worth tracking (names from general knowledge; company numbers to be confirmed on EDGAR
**[unverified]**): RA Capital, Baker Bros, Perceptive, OrbiMed, Deerfield, BVF, EcoR1, Boxer, Avoro, RTW, Cormorant, Venrock
Healthcare, Commodore, Fairmount, Vivo, Samsara, Frazier Life Sciences, TCG Crossover, Suvretta. Their 13D/13G and Form 4
filings are much quicker than 13F.

## 7. Science sources

| Source | What | Access and cost | Terms | History kept? | Effort | Value |
|---|---|---|---|---|---|---|
| **Europe PMC** | Papers plus preprints in one API | [REST](https://europepmc.org/RestfulWebService), no key **[tested]** | Per-article copyright; no wholesale republication | Index dates per record | Low | High for the effort |
| **bioRxiv / medRxiv** | Preprints with licence per item | [API](https://api.biorxiv.org/), no key | Per-preprint licence; bulk full text may not be re-hosted ([terms](https://www.biorxiv.org/tdm)) | Numbered versions | Low | Medium-high |
| PubMed | Abstracts | [E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25497/); 3 calls a second, 10 with a free key; **asks for an e-mail** (not tested) | Credit NLM; some abstracts are publisher copyright | Records get revised | Low | Medium |
| **Crossref and Retraction Watch** | Retractions and corrections | [API](https://api.crossref.org/) no key; [daily data file](https://gitlab.com/crossref/retraction-watch-data) | Open | Dated | Low | Medium: rare but sharp |
| OpenAlex | Authors, institutions, citations | API; pricing model changed in 2026, free key gives 10x budget ([docs](https://help.openalex.org/api-reference/authentication)) | CC0 | Changes | Low | Low-medium |
| PubPeer | Critiques of published papers | No public API; ask first | Unclear | Changes | - | Low-medium |
| **Conference abstracts** | ASCO, ASH, ESMO, AACR and others | A different site per meeting | Society copyright. ASH forbids public republication ([policy](https://www.hematology.org/meetings/annual-meeting/abstracts/copyright-and-reuse-policy)) | - | High | **High in season** |
| Patents: USPTO | Grants, challenges | PatentsView search paused since March 2026 ([notice](https://www.uspto.gov/subscription-center/2026/patentsview-migrating-uspto-open-data-portal-march-20)) | Public domain | - | Medium | Low-medium |
| Patents: EPO | Families, legal status | Free to 4 GB a week after registration ([EPO](https://epo.org/en/searching-for-patents/data/web-services/ops)) | Reuse allowed | - | Medium | Medium; owner decision |
| Patents: Lens.org | - | **API needs an institutional subscription; investment use counts as commercial** ([terms](https://about.lens.org/lens-api-terms-of-use/)) | - | - | - | **Avoid** |
| Grants: NIH RePORTER, USAspending | Awards and contracts | Open APIs, no key | Public | Yes | Low | Low-medium, for the few grant-dependent companies |

**Conference abstract releases are fixed, known catalysts.** Example: ASH 2026 regular abstracts went online 4 November at
09:00 New York time, late-breaking ones follow on 7 December ([ASH embargo policy](https://www.hematology.org/newsroom/annual-meeting-press/embargo-policy)).
ASCO releases regular abstracts on the Thursday about a week before the meeting. There is no open combined feed. Practical
route: a calendar of release times, then fetch only the abstracts of watched companies, keep them private and quote briefly.

## 8. News, social media, macro and policy

| Source | Access and cost | Terms | Value |
|---|---|---|---|
| **Trade press headlines** (Endpoints, Fierce Biotech, STAT, BioSpace, BioPharma Dive) | RSS; addresses to confirm per outlet **[unverified]** | Headline and link only; no full text | High for the effort |
| GDELT | Free API, credit required ([terms](https://www.gdeltproject.org/about.html)); throttled on test **[tested]** | Open | Low-medium: thin for small companies |
| Finnhub company news | Free key, 60 calls a minute | Closed; personal use | Medium |
| NewsAPI.org | Free tier is for development only; $449 a month otherwise ([pricing](https://newsapi.org/pricing)) | Closed | Avoid |
| **X / Twitter** | No free tier for new developers since Feb 2026; roughly $300 a month for our use (agent's estimate) **[unverified]** | Closed | Out of reach, though biotech discussion there matters |
| **Reddit** | New API access needs approval since Nov 2025; restrictions on AI use **[unverified exact wording]** | Closed | Low signal anyway |
| StockTwits | Closed to new developers | Closed | Avoid |
| Bluesky | Open stream, no key ([docs](https://docs.bsky.app/blog/jetstream)) | Open protocol | Low-medium |
| Short-seller reports | Firms' own sites | Personal reading | Medium as a risk flag. Hindenburg closed in January 2025 |
| Deals and licensing | 8-K item 1.01 and press releases | Open | High. Closed deal databases are expensive |

| Macro and policy source | Access | Value |
|---|---|---|
| **US Treasury yields** | [Daily CSV](https://home.treasury.gov/resource-center/data-chart-center/interest-rates), no key **[tested]** | High, trivial |
| FRED | Free key required ([terms](https://fred.stlouisfed.org/docs/api/terms_of_use.html)) | Medium |
| Federal Register, Congress.gov | No key / free key | Medium, sector level |
| FDA and Fed calendars | Web pages | Medium |

**Interest rates and biotech.** No study specific to XBI was found. The standard argument is that companies whose value lies
in distant profits react most to rates ([Dechow, Sloan, Soliman 2004](https://www.bus.umich.edu/facultyresearch/researchcenters/centers/tozzi/duration.pdf)).
Suggest measuring XBI's own sensitivity in the historical study.

**Policy items reported for late 2026 (from the linked secondary sources; confirm before relying on them):**
- BIOSECURE reportedly became law in December 2025, with a government list of companies of concern due around December 2026
  ([Akin](https://www.akingump.com/en/insights/alerts/biosecure-act-becomes-law)). Relevant for biotechs that depend on
  certain Chinese contract manufacturers.
- Tariffs on patented drug imports reportedly from September 2026, with orphan drugs exempt
  ([Ropes & Gray](https://www.ropesgray.com/en/insights/alerts/2026/04/100-on-brand-us-imposes-new-tariffs-and-key-exemptions-on-patented-pharmaceuticals)).
- "Most favoured nation" price deals concern large drugmakers.

Policy moves the sector and rarely one small company. A weekly agent screen of the Federal Register and FDA feeds is enough.

## 9. Important but overlooked streams

The owner asked for this specifically. The test for inclusion: a specialist biotech analyst checks it, a generalist does not,
and it can be had from open sources. Ranked by value for effort.

### 9.1 Manufacturing: the contract manufacturer's inspection record (high)
- **Why it matters.** Trade analyses of the rejection letters FDA published in 2025 find that 74% of 202 letters cite quality
  or manufacturing problems ([Pharma Manufacturing](https://www.pharmamanufacturing.com/all-articles/article/55302937/fdas-crls-reveal-74-of-applications-rejected-for-quality-manufacturing-issues))
  and 56% of 89 letters for unapproved products cite facility inspections ([analysis](https://insider.thefdagroup.com/p/an-analysis-of-89-fda-crls)).
  Not peer-reviewed, and the analyses categorise differently.
- **Example.** A fill-and-finish plant in Indiana (formerly Catalent, owned by Novo Nordisk since December 2024) caused
  rejections for Scholar Rock's apitegromab in September 2025 and for a Regeneron drug in July 2025. No efficacy or safety
  issue was cited ([pharmaphorum](https://pharmaphorum.com/news/manufacturing-issues-block-fda-nod-scholar-rock-sma-drug),
  [Fierce Pharma](https://www.fiercepharma.com/manufacturing/regeneron-says-novo-plant-problems-caused-crl-and-will-delay-2-eylea-decisions)).
  The risk sat at another company's facility and was public beforehand.
- **Why it is overlooked.** You first need to know who makes the product, which is buried in the annual report and supply
  agreements, and then follow that site in FDA databases that no finance site shows.
- **How.** An agent extracts "manufactured by X at Y" from the annual report for the 30-60 companies with a pending
  application, then checks warning letters and inspection results weekly. FDA sources in section 4.
- **Caveat.** Most inspection findings are minor. The serious classification ("official action indicated") and warning letters
  are the signal. Inspection data lags by months, and trade press often reports first.

### 9.2 Wording changes between consecutive filings (medium-high)
- Cohen, Malloy and Nguyen ("Lazy Prices", [Journal of Finance 2020](https://doi.org/10.1111/jofi.12885)): companies that
  change their report language underperform, the market does not react on the filing day, and changes in risk factors are
  among the most informative.
- For biotech: a new or removed going-concern paragraph; the runway sentence shifting ("into Q2 2027" becomes "into Q4 2026");
  a new risk factor naming a manufacturer; softer wording about an FDA meeting; a dropped guidance date.
- Comparing two long documents and saying what changed is exactly where an agent beats a script. Source: EDGAR.
- Caveat: the study covers all listed companies. For 200 companies over six months there will be few events.

### 9.3 Financing structure (high; evidence by example)
What to extract from exhibits and footnotes:
- cash runway against the date of the next catalyst. Companies tend to raise money right after good data, so "good news" does
  not always help the shareholder;
- **loan covenants**: venture lenders often require a minimum cash balance and can call the loan after a "material adverse
  change". Example: a default notice to Better Therapeutics citing its minimum-cash covenant
  ([report](https://www.marketscreener.com/quote/stock/BETTER-THERAPEUTICS-INC-128898694/news/Better-Therapeutics-Inc-Receives-Notice-of-Default-from-Hercules-Capital-Inc-46320519), secondary);
- warrants and their exercise prices, at-the-market usage, lock-up expiry dates, resale registrations after private placements;
- the "baby shelf" limit: a company with under $75M of freely traded shares may sell at most a third of that per year
  ([explanation](https://cooleypubco.com/?p=7132)). Mostly below our size floor, but fallen companies end up here.
No systematic study was found. Agents are well suited to it.

### 9.4 Programmes that disappear quietly (medium-high)
- Big pharma routinely drops programmes from quarterly pipeline charts without a press release
  ([AbbVie example](https://www.biospace.com/abbvie-removes-two-early-stage-cancer-assets-from-pipeline),
  [Roche](https://www.fiercebiotech.com/biotech/roche-sheds-clutch-licensed-drugs-pipeline-cull)). For a small company with a
  partnered drug, **the partner's chart is the signal**
  ([Merck and Sutro](https://www.fiercebiotech.com/biotech/merck-abandons-sutro-partnered-il-2-drug-routine-pipeline-prioritization)).
- How: save weekly copies of ~200 company pipeline pages and ~20 big-pharma pipeline documents; an agent says what changed.
  The [Wayback Machine API](https://archive.org/developers/wayback-cdx-server.html) **[tested]** gives some history, but its
  coverage of small companies is patchy. Check each site's terms.
- Caveat: website redesigns create false alarms. No study of returns was found.

### 9.5 Read-through from drugs in the same class (high)
A competitor's readout, rejection, hold or safety problem on the same target or mechanism moves the whole group. Generalist
frameworks do not link companies by mechanism. Build a "class-mates" list per company once (Open Targets, ChEMBL, registry
searches) and route every such event to the agents of all class-mates.

### 9.6 Human-genetics support for the target (high as background, not as timing)
Drugs whose target is supported by human genetic evidence succeed about twice as often
([Nelson et al. 2015](https://doi.org/10.1038/ng.3314)); a 2024 update finds 2.6 times
([Minikel et al. 2024](https://doi.org/10.1038/s41586-024-07316-0) **[checked: link resolves]**). Available per target from
[Open Targets](https://platform.opentargets.org/). One extra input for the success estimate in every thesis.

### 9.7 Smaller items worth having
| Stream | Why | Access | Value |
|---|---|---|---|
| Company's rejection announcement against FDA's published letter | Companies sometimes downplay | openFDA, when FDA publishes | Medium |
| EMA "under evaluation" list | Shows EU filings never announced, and long clock-stops | Monthly file | Medium |
| Label changes (DailyMed) | New warnings or indications for marketed products | [API](https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm), no key **[tested]** | Medium, commercial-stage only |
| Retractions of a programme's founding papers | Rare but severe | Crossref | Medium; one-off check per programme |
| Departure of the chief medical or scientific officer before a readout | Biotech lore; no evidence found | 8-K item 5.02 | Plausible |
| Late-breaking slot at a conference | Suggests notable data; no evidence found | Conference programmes | Low-medium |
| Market value below cash | Simple screen for "pipeline valued at nothing" | Filings and price | Medium |

### 9.8 Sounds clever, not worth it here
| Stream | Why not |
|---|---|
| Trading-halt feed as a speed edge | Works **[tested]**, but the edge is seconds; we decide once a day |
| New brand trademarks, web domains, certificate logs | Slow, noisy; the certificate service failed on test |
| Generic-name assignments (INN) | Predictable and months behind |
| Securities class actions | Filed after the fall |
| Citizen petitions, patent challenges, court dockets | Few clinical-stage companies affected; keys or manual work |
| Foreign exchange disclosures (Korea, Japan, Australia) | Keys, terms and language barriers; case by case for known partners |
| EU short-position registers (including the Dutch AFM) | Only cover EU-listed shares; our universe is mostly US-listed. Named short-sellers are information the US does not publish, so worth revisiting if European listings are added |
| Adverse-event mining | Few marketed products; noisy and late |

### 9.9 A specialist's checklist before a binary readout (candidate for the thesis template)
1. The trial design now against the design at the start: endpoint, size, completion date changed?
2. Is the primary endpoint one the regulator accepts for approval in this disease?
3. Does the trial size fit the effect seen in phase 2? Was that effect a subgroup or after-the-fact finding?
4. How did drugs of the same class or target do in this disease?
5. Genetic support for the target; base rate for this phase and disease.
6. Cash runway against the readout date; shelf and at-the-market capacity; loan covenants; warrants.
7. What happens after the readout: a likely share sale on good news, and the floor on bad news (market value against cash).
8. Insider and specialist-fund behaviour in the run-up.
9. Management changes in the last six months; auditor change; late filings.
10. Wording changes in the latest quarterly report.
11. For an FDA decision: who manufactures it and what is that site's inspection record?
12. Does the partner still list the programme at the same phase and timeline?
13. Any retraction or expression of concern on the key papers?
14. Written down beforehand: what counts as success, the expected price reaction, and what would change the thesis.

A historical check of which of these signals actually preceded past events, including false alarms, is in
[CASE-FORENSICS.md](CASE-FORENSICS.md).

## 10. Alternative data

Mostly noise for this fund. The few with some merit:

| Source | Access | Verdict |
|---|---|---|
| Job postings on company career boards | Public JSON on common platforms **[unverified terms]**; save weekly | Maybe later: commercial hiring before an approval, or cuts. Small companies post few jobs |
| Layoff notices (WARN) | State sites; [open scraper](https://warn-scraper.readthedocs.io/) | Low-medium; usually also in a filing |
| Court dockets (CourtListener) | Free token now required **[tested]**; low free limits | Low-medium |
| Wikipedia page views | Open; asks for a contact in the request | Low |
| Google Trends | Official API is invitation-only; scraping is unreliable | Skip |
| Web traffic, prescriptions, import records, LinkedIn, Glassdoor | Closed or scraping forbidden | Skip |

## 11. Sources to avoid

| Source | Reason |
|---|---|
| WHO ICTRP | Research use only; automated service unavailable |
| PR Newswire (automated) | Terms ban robots and AI use |
| Lens.org API | Institutional subscription; investment use is "commercial" |
| Stooq | Blocks scripts; no published terms |
| NewsAPI free tier | Development use only |
| X, StockTwits, Reddit | Paid, closed or approval-gated |
| iShares automated download | Terms ban bots; download by hand |
| Closed catalyst calendars, automated | Terms restrict reuse; some dates are estimates |
| Paid transcript services | Closed, redistribution forbidden |
| CTO trial-outcome labels | Partly derived from share prices: circular |
| Nasdaq Daily List | About $3,500 a month |
| The registry's internal history route as a dependency | Undocumented and refusing scripts |
| Alpaca "paper" account | Still a broker sign-up |

## 12. Test calls made on 2026-11-15

All anonymous, no key, 1-3 records, generic client name, no personal details. Calls marked "me" were repeated by me after
the research agents; the rest were made by the agents.

| Source | Result |
|---|---|
| ClinicalTrials.gov API v2 | Works; data stamp 2026-11-13; 781 industry records updated since 12 Nov (me) |
| ClinicalTrials.gov internal history route | **403** on two address forms (me) |
| openFDA approvals, shortages, Orange Book | Work |
| openFDA rejection letters | Works; 458 letters; last update 2026-08-13 (me) |
| openFDA search for Casgevy | Not found: cell and gene therapies missing (me) |
| Federal Register API | Works; 3,105 FDA advisory-meeting notices (me) |
| EMA orphan-designation file | Works (me) |
| Europe PMC | Works; 1,229 preprints dated 2026-11-10 (me) |
| bioRxiv API, NIH RePORTER, Crossref | Work |
| US Treasury yield CSV | Works; latest row 2026-11-13 (me) |
| ARKG holdings CSV | Works; dated 2026-11-13 (me) |
| SPDR XBI holdings file | Works at the new address (me) |
| Nasdaq symbol directory | Works (me) |
| FINRA daily short-volume file | Works |
| Nasdaq trading-halt feed, DailyMed, Wayback Machine | Work |
| Stooq | **Blocked** by a browser check |
| iShares IBB holdings | Returned a web page, not the file |
| GDELT | Throttled |
| CourtListener | Now needs a token |
| Certificate-log search (crt.sh) | Failed |
| Cboe option quotes | Bot protection |
| Wikipedia page views | Worked, but its policy asks for a contact in the request; one call was sent with a generic client name before the agent knew |

**Not tested because they require contact details or registration:** SEC EDGAR, PubMed E-utilities, AACT, FDA Data Dashboard
API, OpenAlex with key, FRED, Tiingo, Massive, EPO. One agent started a single request to SEC full-text search by mistake; the
permission system blocked it and nothing was sent.

## 13. What to build first, and what to save from day 1

### Top 10 by value for effort
| # | Stream | Why first | Effort |
|---|---|---|---|
| 1 | **SEC filings feed** (8-K, share-sale filings, insider trades, late-filing notices, 13D/G) via edgartools | Highest signal, permanent timestamps, free | Low |
| 2 | **Daily copies of trial records, compared by script** | The only way to see registry changes; irreplaceable history | Low |
| 3 | **Daily closing prices, raw, plus our own split table** | Needed for everything | Low |
| 4 | **Quarterly and annual reports: cash, runway, going-concern, and the comparison with the previous report** | Best-evidenced overlooked signal; decides dilution risk | Medium |
| 5 | **Our own catalyst calendar**, versioned | The fund is organised around catalysts; no open calendar exists | Medium |
| 6 | **Company investor-relations feeds** | Fastest allowed news trigger | Low-medium |
| 7 | **Universe and benchmark files**: XBI and ARKG holdings, Nasdaq symbol and non-compliant lists | Trivial, and history is lost otherwise | Low |
| 8 | **Regulatory confirmations**: openFDA, FDA feeds and biologics pages, Federal Register, EMA files | Easy official sources | Low |
| 9 | **Short interest and borrow fees**; Treasury yields | Free context on positioning and rates | Low |
| 10 | **Europe PMC and bioRxiv**, plus a conference abstract calendar | One keyless API for the science; abstract dates are known catalysts | Low, calendar medium |

Next tier, once the above runs: manufacturer inspection tracking for companies with a pending decision; partner and company
pipeline-page copies; class-mates lists; trade-press headlines; specialist-fund filings; genetics and base-rate table.

**Before all of it: the linking table** (company number ↔ ticker ↔ sponsor names ↔ drug codes ↔ trial numbers), with a
one-time human check.

### Save from day 1, even before the spec is finished
These lose their history every day. A small script that only saves files, with no analysis, would be enough.
| What | How often |
|---|---|
| Trial records for the watched companies | Daily |
| XBI, ARKG (and SBIO) holdings files | Daily |
| Nasdaq symbol directory and non-compliant list | Daily |
| Raw closing prices and volumes as fetched | Daily |
| Interactive Brokers borrow file | Daily |
| Option prices for companies with a catalyst within 60 days (if used) | Daily |
| Company pipeline pages and partner pipeline documents | Weekly |
| Investor presentations as found on company sites | When changed |
| EMA files and "under evaluation" list | Daily / monthly |
| Our own universe list with its criteria | Monthly |
| News items as seen: headline, link, time | Continuous |

This needs the owner's go-ahead, because it is the first code in the project and some files have terms to accept (section 15).

## 14. Open questions the data cannot answer yet
- Whether registry edits, pipeline-page changes or specialist-fund moves carry price information for small biotechs. No good
  study exists. Our forward experiment and the historical study are the test.
- How many catalysts will resolve in six months for ~200 companies. This sets what the experiment can show; count it from the
  calendar once built.
- Real spreads and trading costs for the smaller names; measure from daily data in the pilot.

## 15. Points for the owner's decision

1. **A contact e-mail for the SEC** (mandatory in every request) and for PubMed. Suggestion: a dedicated project address,
   kept out of the public repository. Nothing touching SEC data can run before this.
2. **Public repository rule.** Proposal: show only our own computed results, short quotes with links, and official
   public-domain data; never raw vendor prices, holdings files, full press releases, abstracts or transcripts. Worth a
   decision record.
3. **Free sign-ups**, each needing an account: a price source (Tiingo and/or Massive); optionally openFDA key, FRED, AACT,
   FDA Data Dashboard, NCBI, EPO.
4. **Price source**, and whether a small paid plan (about $20-30 a month) is acceptable later for delisted history.
5. **"What is priced in"**: accept Yahoo's personal-use grey zone for a daily option snapshot, pay for options data, or use
   the cash-versus-market-value screen and historical move sizes only.
6. **Newswires**: company feeds and EDGAR only (cleanest), or also Business Wire and GlobeNewswire feeds.
7. **Webcasts**: transcribe public calls locally or leave them out of version 1.
8. **Start the day-1 archive now**, before the spec, and where it is stored and backed up.
9. **Registry-edit signals and the other thin-evidence streams**: make them formal hypotheses in the spec, with the measure
   fixed in advance.
10. **Social media**: accept that it is out of reach for free.

## 16. Not verified
- Terms of use of ClinicalTrials.gov, AACT, SSGA (XBI file), Interactive Brokers' borrow file, Bluesky, Europe PMC and the
  trade-press feeds; exact free limits of Tiingo and Massive.
- Dutch statute text on text-and-data mining (cited through secondary sources).
- Exact filing deadlines quoted from standard rules; the list and company numbers of specialist funds.
- All 2026 policy and FDA-leadership items (secondary sources only).
- All volume and token estimates.
- The 2026 preprint on registry edits was read in summary only.
