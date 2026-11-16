# F. Overlooked information streams for small/mid-cap biotech (research 2026-11-15)

Scope: streams that a specialist biotech analyst checks and a generalist (or a price+news+fundamentals LLM framework) does not. The basic catalogue (CT.gov, openFDA, EDGAR main forms, PubMed, etc.) is covered elsewhere and only mentioned here for an overlooked *angle*.
Method: web search of primary sources plus a few anonymous test calls (results in section 0). Anything marked **unverified** was not confirmed from a primary source. Anything written from memory is labelled that way.

## 0. Test calls made today (2026-11-15, anonymous, no key)

| Endpoint | Result |
|---|---|
| Wayback CDX `https://web.archive.org/cdx/search/cdx?url=vrtx.com/our-science/pipeline/&limit=3` | Works. Returned 3 captures (July 2022) with timestamp + content digest. Digest changes = page changed. |
| Nasdaq halts RSS `https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts` | Works. XML with symbol, halt time, `ReasonCode` (e.g. T1), resumption times. TTL 1 min. |
| openFDA CRL `https://api.fda.gov/transparency/crl.json?limit=1` | Works. `total: 458` letters; `last_updated: 2026-08-13` (so not refreshed for ~3 months: "promptly published" is not quite true in practice). |
| DailyMed `https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?published_date=...` | Works. JSON list of new/updated labels (SPL) by date. |
| CourtListener v4 search without token | **Fails**: "Authentication credentials were not provided" (needs a free account token now). |
| crt.sh JSON | **Failed** (502 twice, then empty). Known to be flaky; not dependable. |
| CT.gov internal history endpoint | 403. The documented API v2 has no version history (see 2.2). |
| AFM short-position CSV (guessed URL) | 500; correct export URL not found. Registers exist as HTML (see 6.1). |
| EU CTIS public portal `https://euclinicaltrials.eu/ctis-public/search` | 200 (web app; no documented public API found). |

---

## 1. Manufacturing / CMC: the contract manufacturer's inspection record (HIGH value)

**What & why.** FDA's published CRLs show that manufacturing/quality, not efficacy, is the most common reason for a rejection. Trade analyses of the CRLs FDA published in 2025: 74% of 202 CRLs (2020-2024, later-approved products) cite quality/manufacturing issues ([Pharma Manufacturing](https://www.pharmamanufacturing.com/all-articles/article/55302937/fdas-crls-reveal-74-of-applications-rejected-for-quality-manufacturing-issues)); 56% of 89 CRLs for unapproved products cite facility-inspection issues ([FDA Group analysis](https://insider.thefdagroup.com/p/an-analysis-of-89-fda-crls)). FDA itself found facility-inspection issues were the fastest-growing cause of BLA CRLs ([Duke-Margolis meeting summary, Jan 2025](https://healthpolicy.duke.edu/sites/default/files/2025-01/Meeting%20Summary_Continual%20Improvement%20of%20CDER%20BLAs.pdf); [Citeline](https://insights.citeline.com/PS155154/Facility-Deficiencies-Drive-Rising-CRL-Rates-For-CDER-Biologics)). Categories differ between analyses; no single peer-reviewed share.
**Concrete example.** The former Catalent fill-finish site in Bloomington, Indiana (Novo Nordisk since Dec 2024) caused a CRL for **Scholar Rock**'s apitegromab (Sept 2025; no efficacy/safety issues cited; shares -13%, and "the stock has generally been weakening since news of the problems at the Catalent plant were first disclosed") ([pharmaphorum](https://pharmaphorum.com/news/manufacturing-issues-block-fda-nod-scholar-rock-sma-drug), [The Pharma Letter](https://www.thepharmaletter.com/biotech-news/scholar-rock-shares-suffer-on-manufacturing-site-woes)) and for **Regeneron**'s odronextamab (July 2025); the site later got an OAI classification ([Fierce Pharma](https://www.fiercepharma.com/manufacturing/regeneron-says-novo-plant-problems-caused-crl-and-will-delay-2-eylea-decisions), [Pharma Manufacturing](https://www.pharmamanufacturing.com/sector/contract-manufacturing/article/55322900/fda-hits-novo-nordisk-indiana-site-with-official-action-indicated-letter)). This is the textbook case: the risk was visible weeks before the CRL, at a *different company's* facility.
**Why overlooked.** You need to know which CDMO makes the product (buried in 10-K "Manufacturing" section, supply-agreement exhibits, sometimes only in trade press), then follow that site in FDA databases that are not on finance sites.
**Open access.**
- Warning letters: all published, HTML ([FDA warning letters](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters)); no key.
- Published 483s: [OII FOIA Electronic Reading Room](https://www.fda.gov/about-fda/office-inspections-and-investigations/oii-foia-electronic-reading-room), PDF, only a subset is posted.
- Inspection classifications (NAI/VAI/OAI), citations, compliance actions, import refusals: [FDA Data Dashboard](https://datadashboard.fda.gov/oii/cd/inspections.htm) (web download, no key) and its [API](https://datadashboard.fda.gov/oii/api/index.htm) (**needs an FDA-issued key with name+email** → not usable under "no sign-ups"; use the web export). FDA warns the classification data is not a complete list of inspections.
- Import alerts: FDA import-alert pages (HTML; not tested).
- Public, US government data: may be shown publicly.
**Point-in-time.** Dashboard updated periodically, history kept, but classification dates lag inspections by months. Snapshot the CDMO list per company from day 1 (it's our own derived data).
**Timing.** Leading (weeks to months before a PDUFA date), but the 483/OAI often surfaces first via trade press or the CDMO's/big-pharma's own disclosure.
**Effort.** Medium: one-time mapping of ~30-60 filers (only companies with a pending BLA/NDA matter) to their CDMO sites; then a weekly diff. LLM is good at extracting "manufactured by X at Y" from 10-K text.
**Value.** High for companies with a PDUFA date in the window; irrelevant for others. Noise: many 483s are minor (VAI); OAI and warning letters are the signal.

## 2. Silent changes (diffing)

### 2.1 Company pipeline pages and big-pharma pipeline PDFs (MEDIUM-HIGH)
**Why.** Programmes are routinely dropped in quarterly pipeline charts or web pages without a press release: AbbVie removed two ADCs from its pipeline page, and BioSpace used the Wayback Machine to date it ([BioSpace](https://www.biospace.com/abbvie-removes-two-early-stage-cancer-assets-from-pipeline)); Roche prunes its list every quarter "typically without providing much of an explanation" ([Fierce](https://www.fiercebiotech.com/biotech/roche-sheds-clutch-licensed-drugs-pipeline-cull)); Merck dropped a Sutro-partnered IL-2 drug as "routine pipeline prioritization" ([Fierce](https://www.fiercebiotech.com/biotech/merck-abandons-sutro-partnered-il-2-drug-routine-pipeline-prioritization)). For a small company, **the partner's chart is the read-through** (Sutro, CytomX cases). Academic work codes pipeline removals as suspensions even when never announced (Mace, UT Dallas working paper, **unverified title**; summary via search only). No returns study on the *website-diff* signal itself found → "plausible, limited evidence".
**Why overlooked.** No event, no feed; you must snapshot.
**Access.** Own scraping of ~200 pipeline pages + ~20 big-pharma quarterly pipeline PDFs (check each site's terms/robots.txt). History: Wayback CDX API (tested, works; no key; no official published rate limit, third-party reports 15-60 req/min, tightened since 2024 ([summary](https://wayback.readthedocs.io/en/stable/usage.html)) → stay at ~1 req/s or slower). Wayback coverage of small-company pages is patchy, so **must archive from day 1**. Showing derived diffs publicly: fine for facts ("programme X no longer listed"); don't republish full page copies.
**Timing.** Leading or coincident (changes often go live with the quarterly report but are not in the press release).
**Effort.** Medium (pages change layout; JS-rendered pages need a headless browser). LLM well suited: "compare these two pipeline tables, what changed (phase, indication, removed, partner)".
**Value.** Medium-high, mostly as a negative signal. Noise: redesigns create false diffs.

### 2.2 ClinicalTrials.gov change history (angle only)
The documented API v2 serves the **current** record only; history is visible on the website's record-versions tab, not via a documented API ([search summary](https://intuitionlabs.ai/articles/clinicaltrials-gov-api-v2-pipeline); internal history endpoint returned 403 today). 23% of trials change the primary outcome between start and latest version ([PLoS-type meta-research, PMC10645365](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10645365/)). Fields worth diffing: primary outcome, enrollment (anticipated→actual), primary completion date, status, locations count/countries, "results first submitted". **Snapshot the ~500-1000 relevant NCT records daily from day 1.** Value: high; effort low (structured JSON, diff by script, LLM interprets).

### 2.3 10-K/10-Q text changes ("Lazy Prices") (MEDIUM-HIGH)
Cohen, Malloy & Nguyen, *Lazy Prices*, J. Finance 75(3):1371-1415 (2020), [doi:10.1111/jofi.12885](https://doi.org/10.1111/jofi.12885), [NBER w25084](https://www.nber.org/papers/w25084): firms that change their annual-report language underperform; long-short ~188 bp/month alpha; **no announcement effect**, the information gets into prices later; changes in risk factors, executive team and litigation sections are most informative; changes predict bankruptcies. Biotech-specific angle: new/removed going-concern paragraph, change in the cash-runway sentence ("into Q2 2027" → "into Q4 2026"), new risk factor naming a CDMO, FDA meeting outcome wording, dropping a guidance date.
**Access:** EDGAR (covered elsewhere). **Effort:** low-medium; **LLM very well suited** (cross-document comparison is exactly the agent's edge). Timing: leading by weeks-months per the paper. Caveat: paper is cross-section of all firms, monthly rebalancing; a 200-stock, 6-month paper fund will see few events.

## 3. Financing structure: the thing that moves small-cap biotech prices most outside data (HIGH)

Elements (all in EDGAR exhibits/notes, which other researchers cover as forms; the angle is *what to extract*):
- **Cash runway vs next catalyst** (runway sentence in 10-Q MD&A). Anecdotes, no systematic study found: companies raise immediately after good data (Xenon $747.5M after Ph3 in 2026, Viking $550M in 2024, Cidara $250M with data in 2025, CytomX fell after its $250M raise) ([search summary of news: BioCentury](https://biocentury.com/article/658761/strong-demand-allows-xenon-dianthus-to-upsize-follow-ons-finance-report)). "Plausible, anecdotal evidence".
- **Venture-debt minimum-cash covenants** (Hercules, Oxford, K2, etc.): Better Therapeutics got a Hercules default notice citing the minimum-cash covenant (Section 7.12) and a material-adverse-change clause, obligations declared due immediately ([MarketScreener](https://www.marketscreener.com/quote/stock/BETTER-THERAPEUTICS-INC-128898694/news/Better-Therapeutics-Inc-Receives-Notice-of-Default-from-Hercules-Capital-Inc-46320519)); X4's agreement requires $20M minimum cash ([summary](https://ca.marketscreener.com/quote/stock/X4-PHARMACEUTICALS-INC-55942346/news/X4-Pharmaceuticals-Inc-Enters-into-Second-Amended-and-Restated-Loan-and-Security-Agreement-42677451/)). Secondary sources; verify in the 8-K exhibit. MAC clauses mean a failed trial can trigger the loan.
- **Baby-shelf limit**: Form S-3 General Instruction I.B.6 caps primary sales at one-third of public float per 12 months when float < $75M ([Cooley PubCo](https://cooleypubco.com/?p=7132); example S-3 stating the limit: [Actuate 2025](https://www.sec.gov/Archives/edgar/data/1652935/000168316825006622/actuate_s3.htm)). Mostly relevant below the project's $300M floor, but companies that fall after a failure enter this regime.
- **Warrants** (exercise prices create resistance levels; pre-funded warrants), **ATM usage** (10-Q subsequent events), **lock-up expiries** after IPO/PIPE, **PIPE resale S-1/S-3** (new supply), **CVRs**.
**Why overlooked.** Exhibits and footnotes, not in data APIs. **LLM well suited** (extract covenant thresholds, warrant tables). Effort medium once, then per filing. Value high (determines whether "good data" helps the shareholder). Timing: leading.

## 4. FDA-published Complete Response Letters as a case library (MEDIUM, as a prior, not a signal)
FDA published 200+ CRLs (2020-2024, approved products) on 10 July 2025 and 89 previously unpublished CRLs for unapproved applications on 4 Sept 2025, saying new CRLs would be published promptly ([openFDA CRL page](https://open.fda.gov/apis/transparency/completeresponseletters); [FDA Law Blog Act II](https://www.thefdalawblog.com/2025/09/radical-transparency-act-ii-fda-releases-89-previously-unpublished-complete-response-letters/)). API tested: 458 letters, last updated 2026-08-13. Redacted for confidential info. Use: base rates of failure reasons (facility, CMC, clinical) by modality to calibrate the thesis; compare company's own CRL press release with the letter (companies sometimes downplay; the published letter exposes that). Historical, so no look-ahead problem when used only as background. Public data, may be shown. Effort low. Value medium.

## 5. Read-through from partners, competitors and foreign exchanges

### 5.1 Same-target / same-class readouts (HIGH, but covered sources)
Angle: build a per-company "class-mates" list once (Open Targets / ChEMBL / CT.gov intervention + condition search) and route every competitor readout, CRL, clinical hold or safety signal to the agents of all class-mates. Classic biotech sector move; generalist frameworks don't link tickers by mechanism. No key needed for Open Targets/ChEMBL (from memory, not re-checked today). LLM very well suited. Value high.

### 5.2 Partner disclosures abroad (MEDIUM, mixed access)
- **Korea DART / OpenDART**: free API but **needs key registration** ([third-party docs](https://pypi.org/project/opendart-py); official site opendart.fss.or.kr not fetched) → excluded for now. Mostly Korean; large KOSPI firms must file some disclosures in English since 2024 ([Korea Times](https://www.koreatimes.co.kr/amp/economy/20231217/major-kospi-listed-companies-obliged-to-issue-public-disclosures-in-english-from-january)). Relevant for licensing deals with Korean partners (e.g. Alteogen, Yuhan, LegoChem types).
- **ASX announcements**: free to read ([ASX](https://www.asx.com.au/markets/announcements)), but a (possibly outdated, 2020) terms page bans spiders/scrapers ([terms, test host](https://www.test.asxonline.com/content/asx/home/legals/terms-of-use.html)) → **do not automate** until the live terms are checked.
- **HKEX news, TDnet/EDINET, RNS, Nasdaq Nordic**: not verified in this round (**unverified**). HKEX 18A Chinese biotechs out-license to US-listed companies; English is generally available on HKEXnews (from memory).
Value medium; effort high for the few companies with such partners. Better: monitor the *US-listed* partner's 10-Q and big-pharma pipeline PDFs (2.1).

## 6. Short-selling disclosures outside the US

### 6.1 EU/UK net-short-position registers (LOW-MEDIUM for this universe)
Under the EU Short Selling Regulation, positions ≥0.5% of issued shares are published by holder name: AFM current and archive registers ([current](https://www.afm.nl/en/sector/registers/meldingenregisters/netto-shortposities-actueel), [archive](https://www.afm.nl/en/sector/registers/meldingenregisters/netto-shortposities-historie)), FCA daily reports ([FCA](https://www.fca.org.uk/markets/short-selling)), CNMV, Central Bank of Ireland (xls), AMF open data ([AMF](https://www.amf-france.org/en/news-publications/news-releases/amf-continues-its-data-strategy-release-short-selling-data-public)). Named holders (which fund is short) is information the US doesn't publish. **But** the universe is mostly US-listed; these registers cover only EU/UK-listed shares (e.g. Euronext/Nasdaq Nordic biotechs, Nasdaq-listed ADRs are *not* covered for the US line). A working CSV export URL for AFM was not found today. Value low unless the watchlist includes European listings; then medium. History is kept (archive registers).

## 7. Exchange notices

### 7.1 Nasdaq non-compliance list (MEDIUM for the lower end)
Daily list of companies failing continued-listing standards (bid price < $1 for 30 business days → 180-day cure; equity, filing delinquencies) ([Nasdaq Listing Center](https://listingcenter.nasdaqomx.com/NonCompliantCompanyList.aspx)). Companies usually also file an 8-K, but the list is one structured place. Signals reverse-split risk / delisting. Mostly below the $300M floor, but fallen names drift there. HTML; terms not checked. Effort low. Value low-medium (lagging confirmation of distress).

### 7.2 Nasdaq trading-halt RSS (LOW for this project)
Tested, works (RSS, TTL 1 min). T1 = news pending, T2 = news released, T12 = additional information requested by Nasdaq ([Nasdaq halt codes](https://nasdaqtrader.com/trader.aspx?id=tradehaltcodes)). It is the earliest machine-readable flag for intraday news, but the project trades at most daily on paper, so being seconds early has no value. Use only as an event trigger to fetch the release. Check nasdaqtrader.com terms before polling.

## 8. Naming, coding and pre-commercial footprints

- **WHO INN proposed lists** (~twice a year; e.g. Proposed List 134, 29 Jan 2026; 82nd consultation had 266 requests, 161 biologics) ([WHO INN](https://www.who.int/teams/health-product-and-policy-standards/inn), [82nd summary](https://www.who.int/publications/m/item/inn-26-647)). A code-number compound getting an INN signals the sponsor is committing to late-stage development. PDF; lagging by months; low effort, **low value** (slow, predictable). USAN not researched (unverified).
- **DailyMed SPL feed** (tested, JSON, no key): new labels / label updates for marketed products of small commercial-stage companies, e.g. new boxed warning, new indication. Good as a source to diff labels (label changes = safety signal or expansion). Medium value for commercial-stage names only; low effort.
- **CMS HCPCS J-codes** (quarterly coding decisions): permanent J-code matters for launch uptake of physician-administered drugs. Not verified this round (**unverified**). Low-medium value, only for launches.
- **USPTO trademarks, domain/cert-transparency (crt.sh), FDA proprietary-name review**: crt.sh failed today; trademark filings for brand names are slow and noisy. **Not worth it** (see section c).

## 9. Legal / quasi-legal

- **FDA citizen petitions and dockets** on regulations.gov: API **requires an api.data.gov key** (DEMO_KEY only for samples) ([GSA docs](https://open.gsa.gov/api/regulationsgov/)). Relevant mainly for generic/biosimilar fights and 505(b)(2) products; low relevance for clinical-stage small caps. Low value.
- **CourtListener/RECAP**: now needs a token (tested). Paragraph IV patent suits matter only for commercial-stage names. Low-medium.
- **Securities class actions**: lagging (filed after the drop). Low value.
- **USPTO patent assignment database** (licences, security interests to lenders): plausible signal of quiet deals/liens, no evidence found; not verified. Low.

## 10. Regulators and HTA beyond FDA approval

- **EMA "Medicines under evaluation"** monthly Excel list (since 2012; Excel since Feb 2021; from Jan 2025 includes indication summary and **restart date after the list of questions**; from Oct 2025 PRIME/OPEN flags) ([EMA](https://www.ema.europa.eu/en/medicines/medicines-human-use-under-evaluation)). Lists INNs, not company names → a company's EU filing that was never press-released, or a clock-stop length, can be inferred. Medium value, low effort. History kept.
- **CHMP meeting highlights/minutes** (oral explanations and withdrawals often precede negative opinions). From memory; not verified this round. Medium value for the few companies with an MAA.
- **EU HTA joint clinical assessments** (mandatory for new oncology drugs and ATMPs since 12 Jan 2025; ~15 ongoing mid-2026; EC publishes an ongoing-JCA spreadsheet) ([EC update July 2026](https://health.ec.europa.eu/latest-updates/updated-list-joint-clinical-assessments-2026-07-08_en)). Reveals EU filings (e.g. daraxonrasib) and evidence gaps; two JCAs were discontinued mid-2026 ([Becaris](https://becarispublishing.com/digital-content/blog-post/two-discontinued-jcas-reveal-emerging-evidence-standards-eu-hta-assessments-gather-pace)). Low-medium value for US small caps (EU pricing is secondary to the US).
- **EU CTIS** (EU trial register under CTR): new transparency rules from 18 June 2024, documents published (protocols etc.), downloads of search results, but **no public API confirmed** ([EMA CTIS](https://www.ema.europa.eu/en/human-regulatory-overview/research-development/clinical-trials-human-medicines/clinical-trials-information-system)). Useful for US companies running EU sites (protocol PDFs sometimes earlier than on CT.gov). Medium-high effort; medium value.
- G-BA/IQWiG, NICE, ICER, PMDA, Health Canada portal, FAERS/EudraVigilance, FDA calendars/FOIA logs: relevant for commercial-stage or large companies; for a 6-month forward test of mostly clinical-stage names, low value per effort. Not verified.

## 11. Science integrity and people

- **Human genetic support for the target** (HIGH value, low effort, static prior): Nelson et al., *Nat Genet* 47:856-860 (2015), [doi:10.1038/ng.3314](https://doi.org/10.1038/ng.3314): share of genetically supported mechanisms rises from 2.0% preclinical to 8.2% approved; estimated that selecting supported targets could double success. Minikel et al., *Nature* 629:624-629 (2024), [doi:10.1038/s41586-024-07316-0](https://doi.org/10.1038/s41586-024-07316-0), [PMC11096124](https://pmc.ncbi.nlm.nih.gov/articles/PMC11096124/): probability of success 2.6x with genetic support, varies by therapy area, rises with confidence in the causal gene. Open Targets Platform gives per target-disease genetic evidence (open, no key; from memory). Agent use: one feature in the success-probability prior per programme. Not a timing signal.
- **Retractions / expressions of concern** on the founding papers: Retraction Watch database is open via Crossref since Sept 2023 (REST API filter `update-type:retraction`, git repo updated daily: gitlab.com/crossref/retraction-watch-data) ([EASE](https://ease.org.uk/2023/09/crossref-acquires-and-opens-retraction-watch-data/)). Example (from memory, verify before use): Cassava Sciences (SAVA), simufilam data integrity questions 2021-2024. Rare event; low effort to check once per programme's key papers; value medium as a red flag. PubPeer has an API (not verified).
- **CMO/CSO departures** (8-K 5.02) shortly before a readout: classic red flag in biotech lore, no systematic evidence found → "plausible, no evidence found". Covered by EDGAR; angle = flag executive changes within 6 months of a readout.
- **NIH RePORTER / SBIR / BARDA / CDMRP / disease foundations**: non-dilutive cash, small relative to market cap. Low value.
- **Conference session titles before abstracts; late-breaker slots**: plausible (a late-breaker slot implies the data are notable), no evidence found. Low-medium.

## 12. Structure of the trade (base rates, priced-in)
- **Enterprise value vs cash** (EV < 0 or near zero = market prices the pipeline at ~0): simple calculation from 10-Q cash + shares; a known biotech screen. No paper verified this round → "plausible".
- **Base rates by phase/indication/modality**: BIO/Informa/QLS "Clinical Development Success Rates 2011-2020" (from memory; check terms), plus Minikel/Nelson above. Use as priors in every thesis.

---

## (a) Top 12 "important but overlooked", ranked by value per effort

1. **Cash runway + financing structure vs next catalyst** — agent extracts runway sentence, ATM/warrant/debt covenant terms and flags "readout before runway end → raise likely right after data".
2. **10-K/10-Q text diff (Lazy Prices)** — agent compares consecutive filings section by section and summarises new/removed risk factors, going-concern and runway changes.
3. **ClinicalTrials.gov self-snapshot diffs** — script diffs daily snapshots; agent interprets changes to primary endpoint, enrollment, completion date, sites.
4. **CDMO inspection status for companies with a PDUFA date** — agent maps product → CDMO site from the 10-K, then checks warning letters/483s/OAI and trade press weekly.
5. **Same-target/same-class read-through** — agent receives every class-mate readout, hold or CRL and writes the implication for its own company.
6. **Partner / big-pharma pipeline charts (quarterly)** — agent diffs partner pipeline PDFs for the small company's partnered asset (dropped, delayed, phase-advanced).
7. **Company pipeline-page diffs** — agent explains what changed on the company's own pipeline page between weekly snapshots.
8. **Genetic support of the target (Open Targets) + phase base rates** — agent adds a documented success-probability prior to each thesis.
9. **EMA medicines-under-evaluation list + CHMP outcomes** — agent spots unannounced EU filings and long clock-stops for its companies' INNs.
10. **FDA published CRLs** — agent compares any new CRL text with the company's press release and uses the library for failure-reason base rates.
11. **DailyMed label diffs (commercial-stage names only)** — agent summarises label changes (new warnings, indications).
12. **Retractions/EoCs on key founding papers (one-off check per programme)** — agent checks Crossref retraction data for the programme's foundational papers.

## (b) Must archive from day 1 (history not kept or not accessible)
- Company pipeline pages and partner pipeline PDFs (Wayback coverage patchy).
- ClinicalTrials.gov records (no history via documented API).
- Nasdaq non-compliance list and halt RSS (current-state feeds).
- AFM/EU current short registers (archives exist, but snapshot is cheap).
- EMA under-evaluation monthly Excel (kept, but download each month anyway).
- Our own derived mappings (product → CDMO, class-mates, runway estimates) with dates, so the agents' "what did we know when" is provable.

## (c) Sounds clever, not worth it here
- **Trading-halt RSS as a speed edge**: real but measured in seconds; useless for a daily paper fund.
- **crt.sh / new domains / USPTO brand trademarks**: noisy, slow, unreliable endpoint (failed today), and brand names are filed years before launch.
- **INN/USAN assignments**: predictable and months behind the decision to develop.
- **Securities class-action filings**: lagging, filed after the price drop.
- **Citizen petitions/regulations.gov, PTAB, ITC, UCC liens, Delaware Chancery**: relevant to few clinical-stage small caps; need keys or manual work.
- **Foreign exchange disclosures (DART, ASX, TDnet)** for the whole universe: keys/terms barriers and language; use only case by case for known partners.
- **FAERS/EudraVigilance signal mining**: small companies have few marketed products; signals are noisy and lag.
- **EU short registers**: only cover EU-listed shares; most of the universe is US-listed.
- **FDA officials' calendars, FOIA logs, adcomm waivers**: rare, hard to tie to a ticker.

## (d) Checklist: what a specialist checks before a binary readout (thesis template)
1. Trial design on CT.gov *as it is now vs at start*: primary endpoint, sample size, completion date changed? Any recent amendments?
2. Is the primary endpoint the one FDA/EMA accepts for approval in this indication (precedent approvals, FDA guidance)?
3. Power: does the sample size fit the effect size seen in phase 2? Was the phase-2 result a subgroup/post-hoc?
4. Class read-through: how did same-target / same-modality drugs do in this indication? Any recent class safety issue?
5. Human genetic support for the target; phase/indication base rate.
6. Cash runway vs readout date; ATM/shelf availability; debt covenants (minimum cash, MAC clause); warrants overhang.
7. Expected post-readout behaviour: will they raise on good news (likely), and what is the downside floor (EV vs cash)?
8. Insider/fund behaviour in the run-up (Form 4 open-market buys, 13D/13G changes) — covered elsewhere.
9. Management changes in the last 6 months (CMO/CSO departure, auditor change, NT filing).
10. 10-Q language changes since last quarter (runway sentence, new risk factors, softer guidance wording).
11. For a PDUFA: who manufactures it, and what is that site's recent inspection record (483/OAI/warning letter)? Any CMC language in risk factors?
12. Partner signals: does the partner still list the programme at the same phase and timeline?
13. Integrity: any retraction/expression of concern on the key papers?
14. Write down beforehand: what result counts as success, expected price reaction, and what would change the thesis.

## Uncertain / not verified
- Mace working paper title; FDA's CRL proposed rule (RIN 0910-AJ16).
- HKEX, TDnet/EDINET, RNS, Nasdaq Nordic access; USAN schedule; HCPCS timetable; PubPeer API; Open Targets/ChEMBL keyless access (from memory).
- ASX automated-access ban comes from a 2020 terms page on a test host.
- Wayback rate limits: no official figure found.
- Terms of use for nasdaqtrader.com RSS and Nasdaq Listing Center pages not checked.
