# C. Clinical and regulatory information streams — catalogue

Research date: 2026-11-15. Researcher: subagent (Opus). Read-only; tiny anonymous test calls only (listed in section 0).
Legend: **[verified]** = checked today in a primary source or by a test call; **[unverified]** = from memory or secondary sources only, check before relying on it.
Volume estimates for the ~200-company universe are rough guesses by the researcher (marked "est.").

---

## 0. Test calls made today (2026-11-15, anonymous, no key)

| Call | Result |
|---|---|
| `GET https://clinicaltrials.gov/api/v2/version` | OK. `apiVersion 2.0.5`, `dataTimestamp 2026-11-13T10:00:06` (data ~2 days old on a Sunday; normally refreshed each weekday [unverified]) |
| `GET .../api/v2/studies?pageSize=1&fields=NCTId,LastUpdatePostDate` | OK, JSON, cursor pagination via `nextPageToken` |
| `filter.advanced=AREA[LastUpdatePostDate]RANGE[2026-11-12,MAX]` (+ `AND AREA[LeadSponsorClass]INDUSTRY`) with `countTotal=true` | OK: 3,146 records updated since 12 Nov (all sponsors), 781 industry-sponsored. So **~250-800 industry record updates per posting day worldwide**; our 200 companies will be a small fraction (est. 5-40/day). |
| `GET .../api/v2/stats/size` | OK: 611,771 studies, average 17 KB per record |
| `GET https://clinicaltrials.gov/api/rss?term=glioblastoma&dateField=LastUpdatePostDate` | OK, RSS 2.0, "last update posted in the last 14 days" |
| `GET https://clinicaltrials.gov/api/int/studies/{NCT}?history=true` (undocumented history endpoint) | **HTTP 403 / non-JSON to a script today.** Not usable as an official route. |
| `GET https://clinicaltrials.gov/AllAPIJSON.zip` (HEAD) | 404 (old bulk URL guess is wrong; use the site's download page or AACT) |
| `GET https://api.fda.gov/drug/drugsfda.json?limit=1` | OK, `last_updated 2026-11-13`, 29,457 applications |
| `GET https://api.fda.gov/drug/drugsfda.json?search=application_number:BLA*` | 486 BLAs (CDER-regulated ones only) |
| `drugsfda search brand_name CASGEVY` / `ZOLGENSMA` | **NOT_FOUND** → CBER cell/gene therapies are not in openFDA drugsfda [verified by test] |
| `GET https://api.fda.gov/transparency/crl.json?limit=1` | OK, 458 CRLs, **`last_updated 2026-08-13`**; newest letter_date 08/07/2026. No CRLs added for 3 months. |
| `GET https://api.fda.gov/drug/orangebook.json?limit=1` | OK (endpoint exists, listed in `download.json`), 48,990 records, `last_updated 2026-11-13` |
| `GET https://api.fda.gov/drug/shortages.json?limit=1` | OK, 1,580 records, `last_updated 2026-11-13` |
| `GET https://api.fda.gov/download.json` | drug endpoints today: drugsfda, orangebook, label, enforcement, event, shortages, ndc; plus transparency/crl |
| Federal Register API, FDA + "advisory committee notice of meeting" | OK, 3,105 hits, no key |
| Federal Register API, FDA + "complete response letters", since 2026-06-01 | 0 hits → the planned CRL proposed rule (RIN 0910-AJ16) is **not yet published** as of today |
| EMA JSON `medicines-output-orphan_designations-json-report_en.json` | OK, 3,310 records, `timestamp 2026-11-15T18:15:29Z` |
| Health Canada DPD API `health-products.canada.ca/api/drug/drugproduct/` | Responds (JSON), test DIN returned `[]` |

Not tested (require contact details or registration): AACT (account), FDA Data Dashboard API (name+email for key), WHO ICTRP crawling (email request), SEC EDGAR (User-Agent must contain contact e-mail).

---

## 1. Clinical trial registries

| Source | Contains | Access / endpoint | Key / limits / cost | Licence & terms | History depth | Update / delay | Point-in-time? | Effort | Value |
|---|---|---|---|---|---|---|---|---|---|
| **ClinicalTrials.gov API v2** | All US-relevant trials: status, enrolment (anticipated/actual), dates (estimated/actual), outcomes, arms, sites, results, document uploads | REST JSON `https://clinicaltrials.gov/api/v2/studies`, `/studies/{nct}`; search syntax `AREA[...]`, `RANGE[...]`; RSS `https://clinicaltrials.gov/api/rss?...` [verified] | No key. No official published rate limit found; third-party docs say ~50 req/min/IP [unverified, e.g. [biomcp docs](https://glama.ai/mcp/servers/@genomoncology/biomcp/blob/117cbf50ecab72819025bb21cc6d6d20afec27d5/docs/backend-services-reference/04-clinicaltrials-gov.md)]. Free. | US government (NLM) data; generally public domain, NLM asks for attribution and not to imply endorsement [unverified — the terms page `clinicaltrials.gov/about-site/terms-conditions` is JS-rendered and could not be read by the fetch tool]. Public excerpts: very likely fine with attribution. | Since 2000 | Data refreshed each weekday (dataTimestamp) [verified today]; sponsor changes post days-weeks after the real event (QC review) | **Website keeps full record history** (every QC-approved version, viewable at `clinicaltrials.gov/study/{NCT}?tab=history`); the **documented API v2 returns only the current version**. Undocumented `api/int/...history` returned 403 to a script today. → **Archive our own daily snapshots from day 1.** | Low | **High** |
| **AACT (CTTI)** | Full CT.gov copy as PostgreSQL (≈50 tables) | Cloud Postgres or downloadable daily/monthly dumps: [aact.ctti-clinicaltrials.org](https://aact.ctti-clinicaltrials.org/) | Free, **account required** (name/email) [verified] | Derived from CT.gov | Since 2012 maintained; past snapshots downloadable ("download the latest database or past versions to compare") [verified, depth not stated] | Daily [verified] | Archived dumps give coarse point-in-time copies; not the per-version history | Medium (Postgres) | Medium (convenient for event studies; overkill for 200 companies) |
| **cthist / ctrdata (open-source R packages)** | Tools that pull CT.gov **historical versions** via the internal endpoint | [cthist](https://cran.nics.utk.edu/cran/web/packages/cthist/refman/cthist.html), [ctrdata](https://rdrr.io/github/rfhb/ctrdata/src/R/ctrLoadQueryIntoDbCtgov2.R) (uses `api/int/studies/%s?history=true`) | Free, open source | Rely on an undocumented endpoint | — | — | Yes (reconstruct versions) — useful for the **case library** only | Medium | Medium (event studies) |
| **EU CTIS** (since 2022/2023) | EU/EEA trials under CTR 536/2014; protocol, status, results summaries | Public portal [euclinicaltrials.eu]; **no documented public API or bulk download** found ([EMA CTIS page](https://www.ema.europa.eu/en/human-regulatory-overview/research-development/clinical-trials-human-medicines/clinical-trials-information-system)); portal uses an internal JSON API (scraped by ctrdata and third-party scrapers) [unverified] | Free | EMA legal notice allows reuse incl. commercial with source acknowledgement ([legal notice](https://www.ema.europa.eu/en/about-us/about-website/legal-notice)) [verified]; automated access not addressed | 2023+ (transition from EudraCT ended Jan 2025 [unverified]) | Unknown; transparency rules revised June 2024 (deferrals of publication) | Overwrites; archive ourselves | High (undocumented) | Low-Medium (US small caps mostly run US trials; duplicates CT.gov) |
| **EudraCT / EU CTR (legacy)** | Pre-2023 EU trials + result summaries | `clinicaltrialsregister.eu` web pages / download per search [unverified] | Free | EMA terms | 2004-2025 | Frozen-ish | — | Medium | Low (history only) |
| **WHO ICTRP** | Aggregates ~17 registries (ChiCTR, jRCT, CTRI, ANZCTR, ...) | Search portal; CSV/XML download of search results; **crawling service needs credentials by e-mail and was "currently not available"** ([crawling service](https://www.who.int/tools/clinical-trials-registry-platform/the-ictrp-search-portal/ictrp-search-portal-crawling-service), [conditions](https://www.who.int/publications/m/item/who-ictrp-crawling-service---conditions-of-use)) | Free for non-business; businesses charged | **Research use only; no marketing/promotional/commercial use** of extracted data ([download page](https://www.who.int/tools/clinical-trials-registry-platform/network/who-data-set/downloading-records-from-the-ictrp-database)) | — | Weekly-ish imports [unverified] | No | High | **Low — avoid** (terms + availability; a "fund", even paper, is arguably not "research") |
| **ISRCTN** | UK-centred registry | Has an API per community knowledge [unverified; `isrctn.com/page/api` returned 404]; ctrdata supports it | Free | Unknown | 2000+ | — | Overwrites [unverified] | Medium | Low |
| **ChiCTR / CDE chinadrugtrials.org.cn** | Chinese investigator trials / NMPA-registered drug trials (CTR numbers) | Web only; no API or terms found [unverified] | Free | Not found | — | — | No | High (Chinese, scraping) | Low (relevant only for in-licensed Chinese assets) |
| **jRCT (Japan), ANZCTR (Aus/NZ)** | National registries | jRCT web only [unverified]; ANZCTR manual Excel export of search results, no API ([FAQ](https://anzctr.org.au/Faq.aspx)) | Free | Not found | — | — | No | Medium-High | Low (ANZCTR has some value: many US small caps run cheap Phase 1 in Australia) |
| **Results postings** (CT.gov results section, EU results, company "clinical trial results" pages) | Summary results after completion | CT.gov `hasResults`, `ResultsFirstPostDate` fields in API v2 | — | — | — | Legally due within 12 months of primary completion, often late or never: only 41% on time per TrialsTracker-based analysis ([The Transmitter](https://www.thetransmitter.org/spectrum/sponsors-of-clinical-trials-may-report-data-late-or-never/)) | Snapshots | Low | Low-Medium (results are usually press-released first; postings mostly lag the market) |

### ClinicalTrials.gov — known traps
- **Estimated vs actual dates**: `primaryCompletionDateStruct.type` = ESTIMATED/ACTUAL. Primary completion = last visit for the primary outcome, not readout date ([CU Anschutz](https://research.cuanschutz.edu/crs/clinical-research-support/clinical-research-administration/clinicaltrials.gov-support/tips-of-the-week-archive/tip-of-the-week-april-2-2020/clinicaltrials.gov-completion-dates-what-they-are-what-they-are-not)). Stated completion dates are often inconsistent with recruitment end ([The Scientist](https://www.the-scientist.com/clinical-trial-reporting-errors-undermine-transparency-70300)).
- **Stale records**: many records are never updated (status UNKNOWN after 2 years without verification; our test record NCT03772535 shows exactly that).
- **Sponsor-name mess**: lead sponsor is free text (subsidiaries, old names, licensors, CROs); build a manual NCT → ticker map per company and re-check monthly.
- **Lag**: changes appear only after sponsor submission + NLM QC; `lastUpdatePostDate` is the posting date, `lastUpdateSubmitDate` the submission date — use both.
- **Endpoint changes**: visible only by diffing outcome modules between versions.

---

## 2. Regulatory sources — FDA (US)

| Source | Contains | Access / endpoint | Key / limits / cost | Licence | History | Update | Point-in-time? | Effort | Value |
|---|---|---|---|---|---|---|---|---|---|
| **openFDA drugsfda** | Applications, submissions (ORIG, SUPPL), action dates, review priority, docs links | `api.fda.gov/drug/drugsfda.json` [verified] | Optional key. Without key **240 req/min, 1,000/day per IP**; with free key 120,000/day ([auth](https://open.fda.gov/apis/authentication/)) [verified] | **CC0**, no attribution required, don't imply endorsement ([licence](https://open.fda.gov/license/)) [verified] | 1939+ | Daily Mon-Fri ([docs](https://open.fda.gov/apis/drug/drugsfda/)) | Overwrites (current state) → snapshot | Low | Medium (confirms approvals; approval itself is usually press-released same evening) |
| — BLA coverage | CDER therapeutic biologics yes; **CBER products (vaccines, cell & gene therapies, blood) NO** | Casgevy/Zolgensma not found [verified by test] | | | | | | | Gap: use CBER pages |
| **Drugs@FDA data files** | Same as above, zipped text tables | [Drugs@FDA download](https://www.fda.gov/drugs/drug-approvals-and-databases/drugsfda-data-files) [unverified URL] | Free | Public domain | — | Weekly [unverified] | No | Low | Low (use openFDA) |
| **openFDA label** (SPL) | Prescribing information, boxed warnings | `api.fda.gov/drug/label.json` | as above | CC0 | 2009+ | Weekly-ish [unverified] | Has `effective_time`/version per label | Low | Low-Medium (label changes, boxed warnings for marketed small caps) |
| **openFDA FAERS** (`drug/event`) | Adverse event reports | `api.fda.gov/drug/event.json` | as above | CC0 | 2004+ | **Quarterly**, lag months [unverified] | Quarterly files | Medium | Low (noisy, lagging; rarely price-moving for small caps) |
| **openFDA enforcement / recalls** | Drug recalls (class I-III) | `api.fda.gov/drug/enforcement.json` | as above | CC0 | 2004+ | Weekly [unverified] | No | Low | Low-Medium (commercial-stage companies only) |
| **openFDA drug shortages** | FDA shortage list | `api.fda.gov/drug/shortages.json` [verified] | as above | CC0 | — | Daily (last_updated 2026-11-13) | No | Low | Low |
| **openFDA Orange Book** (new endpoint) / Orange Book data files | Patents, exclusivities for NDAs | `api.fda.gov/drug/orangebook.json` [verified exists]; files at [Orange Book data files](https://www.fda.gov/drugs/drug-approvals-and-databases/orange-book-data-files) [unverified URL] | as above | CC0 | — | Daily / monthly files | No | Low | Low (long-horizon; matters for M&A/generic-entry stories, not 6-month horizon) |
| **Purple Book** | Licensed biologics, exclusivity, biosimilar interchangeability | Monthly CSV/XLSX ([downloads](https://purplebooksearch.fda.gov/downloads)) [verified: Feb 2020 - Oct 2026] | Free | Public domain | 2020+ monthly archive | Monthly | **Yes, monthly files are dated** (and carry change flags N/U/R) | Low | Low |
| **openFDA CRL endpoint** | Redacted complete response letters (NDA/BLA), incl. pending/withdrawn since Sept 2025 | `api.fda.gov/transparency/crl.json` [verified]; table [open.fda.gov/crltable](https://open.fda.gov/crltable/) | as above | CC0 | 2002?-2026; 458 letters | "Infrequently" ([docs](https://open.fda.gov/apis/transparency/completeresponseletters/)); **last_updated 2026-08-13, newest letter 2026-08-07** [verified] | Static docs | Low | Medium (companies disclose CRL by 8-K/PR first; FDA's text later reveals **what the company didn't say** — e.g. hidden efficacy vs CMC issues; 74% of CRLs cited quality/manufacturing issues per [Pharma Manufacturing](https://www.pharmamanufacturing.com/all-articles/article/55302937/fdas-crls-reveal-74-of-applications-rejected-for-quality-manufacturing-issues)) |
| **Novel drug approvals pages (CDER)** | List of NMEs approved per year | [Novel Drug Approvals 2026](https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2026): 48 approvals, latest 2026-11-09 [verified] | Free | Public domain | 2011+ pages | Same day/next day | No | Low (HTML table) | Medium (confirmation) |
| **CBER approvals** (cell/gene therapy, vaccines) | "Biological approvals by year", "Approved Cellular and Gene Therapy Products" | fda.gov HTML pages [unverified URLs] + RSS "What's New: Biologics" | Free | Public domain | — | Days | No | Medium (HTML) | Medium (many small caps are CGT) |
| **FDA RSS feeds** | Press releases, MedWatch, recalls, What's New Drugs, What's New Biologics | [feed list](https://www.fda.gov/about-fda/contact-fda/subscribe-podcasts-and-news-feeds) [verified]; no RSS for approvals, warning letters or adcomms | Free | Public domain | — | Minutes-hours | No | Low | Medium |
| **Advisory committee calendar + briefing docs** | Meeting dates, briefing docs (posted ≥2 business days before), votes | [AdComm calendar](https://www.fda.gov/advisory-committees/advisory-committee-calendar) (HTML; **empty today** [verified]); Federal Register notice of meeting ≥15 days ahead (API, below) | Free | Public domain | — | — | No | Medium | **High** when they happen, but **rare now**: 14 meetings in 2025 vs 38 in 2024 ([CNHR/STAT](https://www.center4research.org/stat-fda-shuns-advisory-committee-meetings/)); 9 in 2026 so far ([RAPS, 30 Sep 2026](https://www.raps.org/resource/fda-call-for-new-adcomm-members-signals-renewed-interest-in-outside-advisors.html)) [secondary] |
| **Federal Register API** | AdComm meeting notices, guidance notices, proposed rules, orphan/PRV notices | `https://www.federalregister.gov/api/v1/documents.json?conditions[agencies][]=food-and-drug-administration&...` [verified] | No key, free | Public domain | 1994+ | Daily (publication days) | Documents are immutable, dated | Low | Medium (adcomm scheduling ~15+ days ahead, policy) |
| **FDA guidance documents** | Draft/final guidances | [Guidance search](https://www.fda.gov/regulatory-information/search-fda-guidance-documents) HTML/Excel export [unverified] | Free | Public domain | — | Weekly | No | Low | Low (sector-level, not company) |
| **Orphan designation database (OOPD)** | FDA orphan designations, dates, sponsor | [accessdata OOPD search](https://www.accessdata.fda.gov/scripts/opdlisting/oopd/) with Excel export ([instructions](https://www.fda.gov/industry/designating-orphan-product-drugs-and-biological-products/instructions-searchable-designation-database)) [secondary] | Free | Public domain | 1983+ | Monthly [secondary] | No | Medium (form + Excel) | Low-Medium (companies announce designations themselves) |
| **Breakthrough / Fast Track / RMAT** | CDER publishes **aggregate** BTD lists of approved products and request counts; individual grants are disclosed by companies [unverified] | fda.gov pages | Free | — | — | — | — | — | Low (use company PRs) |
| **Priority review vouchers / CNPV** | Rare pediatric PRV awards; **Commissioner's National Priority Vouchers** (1-2 month review target after complete filing) | [FDA press release, first 9 CNPV recipients, 16 Oct 2025](https://www.fda.gov/news-events/press-announcements/fda-awards-first-ever-national-priority-vouchers-nine-sponsors) [verified via search] | Free | Public domain | 2025+ | Ad hoc press releases | No | Low | **High** for named companies (e.g. RMC-6236 Revolution Medicines, bitopertin Disc Medicine, DB-OTO Regeneron) — compresses the catalyst clock |
| **Warning letters** | Warning letters incl. CMOs/CDMOs and sponsors | [Warning letters page](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters) (HTML table + export) [unverified]; Data Dashboard `compliance_actions` | Free | Public domain | 1996+ | Weekly (Tuesdays) [unverified] | No | Medium | Medium (a warning letter or OAI at a key CMO → CRL risk for pending BLAs; needs a company→CMO map, which is hard) |
| **FDA Data Dashboard API** (inspection classifications NAI/VAI/OAI, citations (483 items), compliance actions, import refusals) | | POST endpoints at [datadashboard.fda.gov API](https://datadashboard.fda.gov/oii/api/index.htm) [verified] | **Key by e-mail registration (name, e-mail, "Self")**; 5,000 rows per call | Public domain [unverified] | 2008+ [unverified] | Monthly-ish; inspection classification lags months [unverified] | No | Medium | Medium (CMO risk); **needs owner decision on registration** |
| **Form 483s** | Inspection observations | Only selected 483s posted in the FDA Reading Room / FOIA; Data Dashboard has citation-level data [unverified] | — | — | — | Lag months | — | High | Low-Medium |
| **Clinical holds** | Not published by FDA. Surface via company 8-K/PR (material event), sometimes CT.gov status change to "Suspended" | SEC EDGAR / PRs / CT.gov `overallStatus=SUSPENDED` | — | — | — | Company discretion; delays happen (e.g. [Advaxis delayed hold disclosure](https://insights.citeline.com/SC029974)) | — | — | **High** (price-moving); detectable partly via CT.gov SUSPENDED/WITHDRAWN status changes |
| **PDUFA goal dates** | Not published by FDA. See section 5 | — | — | — | — | — | — | — | **High** |

---

## 3. Regulatory sources — outside the US

| Source | Contains | Access | Terms | Update | Point-in-time | Effort | Value |
|---|---|---|---|---|---|---|---|
| **EMA JSON/Excel data files** (18 files: medicines/EPARs, post-authorisation, referrals, PIPs, orphan designations, PSUSAs, DHPCs, shortages, news, **events & meetings**, all documents) | | `https://www.ema.europa.eu/en/documents/report/...json-report_en.json` ([list](https://www.ema.europa.eu/en/about-us/about-website/download-website-data-json-data-format)) [verified, orphan file works] | Reuse incl. commercial with acknowledgement of EMA as source ([legal notice](https://www.ema.europa.eu/en/about-us/about-website/legal-notice)) [verified] | **Twice daily** (06:00 and 18:00 CET) [verified] | Overwrites → snapshot daily | **Low** | Medium |
| **CHMP highlights / agendas / minutes** | Monthly CHMP meeting: positive/negative opinions, **list of products under evaluation (agenda)**, oral explanations | EMA web pages + documents JSON (filter by document type) [unverified detail] | as above | Monthly (highlights Friday of CHMP week) | Documents dated | Medium (PDF parsing) | Medium (EU opinions move US small caps less than FDA; oral explanation listed in agenda = negative-opinion risk signal) |
| **EMA medicines under evaluation** | Monthly list of INNs/therapeutic areas under evaluation (no company names for non-generics) [unverified] | EMA page/Excel | as above | Monthly | — | Low | Low |
| **EMA PRIME, orphan designations** | PRIME list (Excel), orphan designations (JSON above) | EMA | as above | Monthly | — | Low | Low |
| **UK MHRA** | Approvals, products (MHRA Products site), GOV.UK content API | GOV.UK search API (`https://www.gov.uk/api/search.json?filter_organisations=medicines-and-healthcare-products-regulatory-agency`) [unverified] | Open Government Licence [unverified] | Daily | No | Medium | Low |
| **Japan PMDA** | Approvals list (English, lagging) | Web/PDF [unverified] | — | Irregular | — | High | Low |
| **China NMPA / CDE** | Acceptances, approvals, BTD lists (Chinese) | Web only [unverified] | — | — | — | High | Low (only for China-partnered assets) |
| **Health Canada** | Drug Product Database API, NOC database | `https://health-products.canada.ca/api/drug/...` [responds today] | Open Government Licence – Canada [unverified] | Nightly [unverified] | No | Low | Low |
| **CMS Part D/B spending** | Spending per drug per year | [data.cms.gov](https://data.cms.gov) API (no key) [unverified] | Public domain | Annual | Yearly releases | Low | Low (commercial-stage only) |
| **CMS IRA negotiation** | Selected drug lists, timeline | CMS fact sheets ([IPAY 2028 list, 27 Jan 2026](https://www.cms.gov/files/document/factsheet-medicare-negotiation-selected-drug-list-ipay-2028.pdf)) | Public domain | Annual (Feb 1 list date) | — | Low | **Low for small caps**: lists are big-pharma blockbusters; expanded orphan exclusion from H.R. 1 (2025) further shields rare-disease small caps ([Milliman](https://www.milliman.com/en/insight/key-takeaways-third-medicare-drug-price-negotiation)) |
| **CMS NCDs** | National coverage determinations (e.g. Aduhelm/CED precedent) | Medicare Coverage Database (downloads) [unverified] | Public domain | Ad hoc | — | Medium | Low |
| **ICER** | Cost-effectiveness reports, draft evidence reports, meeting calendar | icer.org PDFs; free registration for some downloads [unverified] | Copyrighted, terms restrict reuse [unverified] | Ad hoc, schedule published ahead | — | Medium | Low-Medium (draft report can move a launching small cap; calendar is a known catalyst) |
| **NICE** | UK HTA guidance; has a syndication API with licence | [unverified] | NICE syndication licence [unverified] | — | — | Medium | Low |

---

## 4. Specific question 1 — which CT.gov changes are detectable, how, and is there price evidence?

**Detectable (by diffing our own daily snapshots of the current record):**
- `overallStatus` transitions: NOT_YET_RECRUITING → RECRUITING → ACTIVE_NOT_RECRUITING (enrolment closed → readout approaching) → COMPLETED; and SUSPENDED / TERMINATED / WITHDRAWN (+ `whyStopped` free text) — the red flags.
- `primaryCompletionDate` / `completionDate` changes and ESTIMATED→ACTUAL flips (ACTUAL primary completion = data collection done; topline usually follows in weeks-months).
- `enrollmentInfo.count` changes and ESTIMATED→ACTUAL (actual < target = under-enrolment).
- Primary/secondary outcome text changes, new arms, dose changes, added/removed sites/countries.
- `hasResults` / `resultsFirstPostDate`; uploaded protocol/SAP documents.

**How:**
1. **Polling (recommended)**: once per weekday, query API v2 with `filter.advanced=AREA[LastUpdatePostDate]RANGE[<yesterday>,MAX]` restricted to our NCT list (or `query.spons=` per sponsor), download full JSON of changed records, store raw JSON with fetch timestamp, diff against previous version. Verified working today; ~1-5 API calls/day for 200 companies (est.).
2. **RSS**: `https://clinicaltrials.gov/api/rss?...&dateField=LastUpdatePostDate` works (14-day window) [verified] — fine as a trigger, but polling the API is simpler and gives full data.
3. **History**: the website keeps every version (record history tab), but there is **no documented API**; the internal endpoint used by `cthist`/`ctrdata` refused a script today (403). Use it at most manually / for the historical case library, not as a pipeline dependency.

**Evidence that registry changes carry price information — thin:**
- Trial *outcomes* clearly move prices, most for early-stage biotechs: Singh, Rocafort, Cai, Siah, Lo, *PLoS ONE* 2022, 13,807 trial outcomes 2000-2020 ([PMC9439234](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9439234/)). Negative events have larger, longer effects ([Hwang, PLoS ONE 2013](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0071966)).
- Registry-change *predictiveness*: a non-peer-reviewed preprint (Research Square, Oct 2026) on version histories of ~4,000 industry trials finds that **cutting enrolment targets and changing primary outcomes predicted later termination**, while primary-completion postponements (in 61% of trials) did not ([preprint](https://www.researchsquare.com/article/rs-11447828/latest)) [secondary summary; not read in full].
- **No peer-reviewed event study found** that links CT.gov registry edits themselves to abnormal returns. Vendor/blog claims exist (AppliedXL "clinical trial alpha" — page not readable here; a Medium practitioner piece) [unverified]. Delay *announcements* do move prices (anecdotes: Minerva −27%, Traws −28%) ([Motley Fool](https://www.fool.com/investing/2019/10/01/heres-why-minerva-neurosciences-fell-over-27-today.aspx)).
- Implication: treat CT.gov diffs as a **hypothesis to test in our own forward experiment**, not an established edge. Natural, cheap event study for the case library: CT.gov versions × daily prices.

---

## 5. Specific question 2 — open recipe for our own catalyst calendar

FDA does not publish PDUFA goal dates. Open recipe:

1. **Company disclosures (primary source of PDUFA dates)**: SEC EDGAR 8-K (Item 7.01/8.01) + attached press releases (EX-99.1), 10-Q/10-K "we expect a PDUFA date of ...". Use the documented `data.sec.gov` submissions JSON per CIK to list new filings daily, then full text search ([EDGAR full-text search](https://www.sec.gov/edgar/search)) for "PDUFA", "target action date", "accepted for filing", "priority review", "advisory committee", "topline". Fair access: ≤10 req/s, **User-Agent must include a name/company and contact e-mail** ([SEC](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)) [verified]. Company IR RSS/PR wires for speed. Let the LLM extract {drug, indication, application type, date, source URL, filing timestamp}.
2. **Derive/verify the date from the review clock** (PDUFA VII, FY2023-2027 commitment letter, [FDA PDF](https://www.fda.gov/media/151712/download)) [verified]:
   - NME NDA / original BLA ("the Program"): standard = **10 months after the 60-day filing date** (≈12 months after submission); priority = **6 months after filing date** (≈8 months).
   - Non-NME original NDA: standard 10 months / priority 6 months **from receipt**.
   - Efficacy supplements: 10 / 6 months from receipt. Class 1 resubmission (after CRL): 2 months; Class 2: 6 months.
   - **Major amendment may extend the goal date by 3 months** (a classic price-moving "PDUFA extension" 8-K).
   - The Day-74 letter tells the sponsor the planned late-cycle meeting / adcomm plan; companies often disclose "no adcomm planned" at acceptance.
   - Holiday/weekend: action often on or before the date; FDA can act early.
   - CNPV products: 1-2 months after complete filing (target, not guaranteed).
3. **Adcomms**: Federal Register API (notice ≥15 days ahead) + FDA adcomm calendar page scrape + briefing docs (2 business days before).
4. **Expected readouts**: company guidance ("topline data in 1H 2027") from 10-Q/10-K/investor decks, cross-checked with CT.gov primary completion date (ACTUAL flip + typical 1-3 months to topline [est.]) and conference abstract deadlines (ASCO, ASH, ESMO, AACR — dates on society sites).
5. **Store every calendar entry versioned** (date first seen, source, each later change) — slips are themselves signals, and this preserves no-look-ahead.

**Closed/free-but-proprietary calendars** (for cross-checking only, terms usually forbid scraping; all closed): BiopharmCatalyst (paid), RTTNews FDA calendar ($99/month; free 30-day view with e-mail) ([RTTNews](https://www.rttnews.com/products/biotechfdacalendar.aspx)), Benzinga FDA calendar, BiopharmaWatch, MarketBeat, Merlintrader (free Google Sheet), Dansfera, TheraRadar ([search summary](https://www.merlintrader.com/free-catalyst-calendar/)). Several state dates may be estimates. Not open source; don't automate against them without reading their terms.

---

## 6. Specific question 3 — FDA changes 2025-2026 affecting data availability/timing

| Change | Status | Source |
|---|---|---|
| HHS RIF announced 27 Mar 2025: ~3,500 FDA positions cut; HHS said reviewers/inspectors not affected | Verified (secondary reporting quoting HHS fact sheet) | [NPR](https://www.npr.org/sections/shots-health-news/2025/03/27/nx-s1-5342414/hhs-doge-rif-rfk-job-cuts), [AABB](https://www.aabb.org/news-resources/news/article/2025/03/28/hhs-announces-reorganization--planned-workforce-cuts) |
| CRL publication: 200+ CRLs (approved apps, 2020-24) published 10 Jul 2025; 89 previously unpublished incl. pending/withdrawn on 4 Sep 2025 with "real-time" promise | Verified (secondary + openFDA endpoint exists) | [RAPS](https://www.raps.org/resource/fda-publishes-200-complete-response-letters-in-tra.html), [Holland & Knight](https://www.hklaw.com/en/insights/publications/2025/09/fda-announces-prompt-disclosure-of-complete-response-letters), [openFDA CRL](https://open.fda.gov/apis/transparency/completeresponseletters/) |
| Real-time CRL release **paused April 2026** after a citizen petition; a batch of 14 released ~July 2026; HHS planned a proposed rule (RIN 0910-AJ16) for Oct 2026 to expand commissioner discretion | Pause verified via secondary ([Applied Clinical Trials, 10 Jul 2026](https://www.appliedclinicaltrialsonline.com/view/fda-pauses-real-time-release-drug-rejection-letters-formalize-policy), [RAPS](https://www.raps.org/resource/fda-plans-rules-to-rein-in-drug-ads-enable-proactive-release-of-crls-and-more.html)). **Proposed rule not found in Federal Register as of 2026-11-15** [verified by API]. openFDA CRL dataset last updated 2026-08-13 [verified]. → Treat FDA CRL release as **irregular**; rely on 8-Ks. |
| Commissioner's National Priority Vouchers: first 9 awarded 16 Oct 2025, 1-2 month review target | Verified (FDA press release via search) | [FDA](https://www.fda.gov/news-events/press-announcements/fda-awards-first-ever-national-priority-vouchers-nine-sponsors) |
| Far fewer advisory committee meetings (14 in 2025 vs 38 in 2024; 9 in 2026 to end Sept); shift to FDA-picked "expert panels"; FDA official: product adcomms "redundant when you have the complete response letters" | Secondary | [CNHR/STAT](https://www.center4research.org/stat-fda-shuns-advisory-committee-meetings/), [BioSpace](https://www.biospace.com/fda/fda-went-against-adcomm-votes-more-held-fewer-adcomms-in-2025), [RAPS](https://www.raps.org/resource/fda-call-for-new-adcomm-members-signals-renewed-interest-in-outside-advisors.html) |
| Government shutdown 1 Oct - 12 Nov 2025: user-fee-funded reviews continued if fees were paid; **no new fee-requiring submissions accepted**; slower communication; risk of goal-date slips after reopening | Secondary; end date 12 Nov 2025 from memory [unverified] | [JD Supra](https://www.jdsupra.com/legalnews/fda-operations-during-the-fy-2026-4823215/), [Caidya](https://www.caidya.com/navigating-fda-regulatory-challenges-during-a-u-s-government-shutdown/) |
| Any 2026 shutdown | Not found [unverified] | — |
| Website/API retirements | None found for openFDA (all drug endpoints live today; **new** `drug/orangebook` and `transparency/crl` endpoints added) [verified]. CT.gov classic site/API v1 retired in 2024 [unverified from memory]; WHO ICTRP crawling service unavailable [verified page text] | test calls; [ICTRP](https://www.who.int/tools/clinical-trials-registry-platform/the-ictrp-search-portal/ictrp-search-portal-crawling-service) |
| PDUFA VIII reauthorisation due by Sept 2027 (current goals FY2023-2027) | Verified (commitment letter period) | [FDA PDF](https://www.fda.gov/media/151712/download) |

---

## 7. Ranked top-8 by value per effort

1. **ClinicalTrials.gov API v2 + own daily snapshots/diffs** — free, no key, verified, high signal (status/date/enrolment/endpoint changes; SUSPENDED/TERMINATED catches holds). Must start archiving on day 1.
2. **SEC EDGAR 8-K/PR feed for PDUFA dates, CRLs, holds, extensions** (covered in another stream, but it is the backbone of the regulatory calendar).
3. **PDUFA clock derivation** (PDUFA VII rules) — zero cost, validates/estimates dates from acceptance announcements.
4. **Federal Register API** — adcomm notices ≥15 days ahead, guidance, rules; no key, immutable, dated.
5. **openFDA (drugsfda, CRL, label, shortages, orangebook)** — CC0, one key-optional API; approvals/CRL text confirmation. Free key raises daily cap.
6. **FDA RSS (press releases, What's New Drugs/Biologics) + novel approvals + CBER approvals pages** — fills the CBER gap in openFDA; fast.
7. **EMA JSON files** (medicines, orphan, events) + CHMP highlights — twice-daily, reusable with attribution, easy.
8. **FDA warning letters / Data Dashboard (OAI inspections)** — CMO risk for pending BLAs; medium effort, needs a CMO map and a registration decision.

**Avoid / deprioritise**: WHO ICTRP (research-only, no commercial use, crawling unavailable); undocumented CT.gov history endpoint as a pipeline dependency (403 today; fine for a one-off case library if terms allow); CTIS internal API (undocumented, low marginal value); ChiCTR/CDE/jRCT/PMDA/NMPA scraping (high effort, low relevance); FAERS (noisy, lagging); IRA negotiation lists (big pharma only); closed catalyst calendars (proprietary terms, estimated dates — cross-check manually at most).

## 8. Points for the owner's decision

1. **SEC EDGAR User-Agent** must contain a contact e-mail — use a dedicated project address? (no personal name needed beyond what SEC asks).
2. **Registrations**: free openFDA API key (raises daily limit from 1,000 to 120,000; probably not needed at our volume), AACT account, FDA Data Dashboard key (name + e-mail). Any of them OK?
3. **Public repo**: openFDA is CC0 and EMA allows reuse with attribution; CT.gov is US government data (attribution to NLM advisable). Showing raw snapshots of these publicly looks fine; do **not** publish ICTRP-derived data or text copied from closed calendars/news.
4. Whether to use the **undocumented CT.gov history endpoint** (via cthist/ctrdata) for the historical case library, given it blocked a script today.
5. Whether CT.gov registry-change signals are a formal hypothesis in the spec (evidence base is thin → good experiment, but don't assume an edge).

## Uncertain / not verified
- CT.gov official rate limit and terms text (JS-rendered page unreadable); ~50 req/min is third-party.
- Exact Drugs@FDA/Orange Book file URLs, warning-letter update cadence, FAERS cadence, OOPD current download format.
- CTIS, ISRCTN, jRCT, ChiCTR API/terms; MHRA/NICE/ICER/Health Canada licences.
- Makary departure and acting commissioner (single secondary source); shutdown end date 12 Nov 2025 (memory).
- Research Square preprint findings (summary only).
