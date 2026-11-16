# E. Market, news, macro/policy and alternative data sources — catalogue

Research date: 2026-11-15 (researcher agent, Opus). Read-only web research, plus a few anonymous test calls (listed in §0).
Scope: paper-money fund, ~200 small/mid-cap US biotechs, end-of-day decisions, run forward for ~6 months, public GitHub repo, no paid services for now.

**How to read this:** every claim has a link. "Unverified" means I could not confirm it on a primary source in this session. Many
pricing and terms details come from vendor pages via search snippets; check the live page before you sign up for anything.
"PIT" = point-in-time behaviour (does the provider keep history, or is it overwritten so we must archive it ourselves?).

---

## 0. Test calls made today (2026-11-15, anonymous, 1-3 records each, no keys, no personal data)

| Endpoint | Result |
|---|---|
| Stooq CSV `stooq.com/q/d/l/?s=xbi.us&i=d` and `iwda.uk` | **Blocked**: returns an HTML page with a JavaScript proof-of-work browser check instead of CSV. Automated CSV download no longer works without a browser. Big finding: Stooq is no longer a drop-in free price source. |
| US Treasury daily par yield curve CSV (`home.treasury.gov/.../daily-treasury-rates.csv/2026/all?type=daily_treasury_yield_curve...`) | **Works**, key-less. Latest row 11/13/2026 (10-yr 5.15%). |
| Nasdaq Trader `nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt` (+ FTP HEAD) | **Works**, key-less; FTP file last modified 2026-11-14. |
| GDELT DOC 2.0 API (artlist, 2 records) | **Throttled**: returned only the "limit requests to one every 5 seconds" message, even on a first call and a retry after 6 s (probably shared-IP throttling). Works in principle, but not reliably from this machine today. |
| ARK `assets.ark-funds.com/.../ARK_GENOMIC_REVOLUTION_ETF_ARKG_HOLDINGS.csv` | **Works**; CSV dated 11/13/2026. |
| SPDR XBI daily holdings xlsx (old URL) | 301 redirect to `https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-xbi.xlsx` (not followed further). |
| iShares IBB holdings CSV (`...1467271812596.ajax?fileType=csv...`) | HEAD says `text/csv`, but GET returned an **HTML page**, not the CSV (needs cookies/browser, or bot-blocking). |
| FINRA Reg SHO daily short-sale volume `cdn.finra.org/equity/regsho/daily/CNMSshvol20261113.txt` | **Works**, key-less, pipe-delimited. |
| Wikimedia pageviews API (Moderna, 3 days) | Works, but **note**: Wikimedia's policy asks for a User-Agent with contact info ([access policy](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/access-policy.html)); I sent a generic UA for one call only. Real use needs a contact UA (a project URL, e.g. the GitHub repo, is acceptable). |
| Cboe delayed quotes JSON (`cdn.cboe.com/api/global/delayed_quotes/options/XBI.json`) | Cloudflare 307 redirect (bot protection); not pursued. |
| SEC FTD page | 403 without a contact User-Agent (SEC requires one — not tested further, per rules). |

---

## 1. Market data: daily prices / volume

**Bottom line:** there is no free, legally clean, survivorship-free, split-adjusted EOD source that also allows public redistribution.
The realistic free path is: (a) one key-based free API for the ~200 tickers (Tiingo or Massive/Polygon free tier) as primary, (b) our own
daily archive of raw (unadjusted) close + volume from day 1, with adjustment done by us from corporate-action records, (c) public repo shows
**our returns and derived charts**, not raw vendor price tables. Delisted-ticker history is the weak spot of every free tier.

| Source | Contents / access | Key? Limits | Cost (free → next tier) | Open/closed; terms (automated personal use / public display) | History / PIT | Traps | Effort | Value |
|---|---|---|---|---|---|---|---|---|
| **Stooq** | EOD CSV, bulk zips | No key, but now **JS proof-of-work wall** (test above) | Free | Closed; no published terms found ([search: no official terms](https://www.quantstart.com/articles/an-introduction-to-stooq-pricing-data)); unverified | Long history; overwritten | Automation blocked as of 2026-11-15 | High now | Low (was medium) |
| **Yahoo via yfinance** | EOD, splits/dividends, options chains, unofficial endpoints | No key; unofficial, rate-limited/breaks | Free | Closed data, Apache-2.0 code. README: "intended for research and educational purposes", Yahoo API "for personal use only", refers to Yahoo terms ([yfinance README](https://cdn.jsdelivr.net/gh/ranaroussi/yfinance@main/README.md)). Redistribution of data not allowed (Yahoo terms, unverified detail) | Adjusted history, delisted tickers usually vanish (survivorship) | Silent schema breaks, IP blocks, adjusted closes rewritten after each split | Low code, high fragility | Medium as backup/options |
| **Tiingo** | EOD (adjusted + raw), IEX intraday, news, fundamentals; REST `api.tiingo.com/tiingo/daily/<ticker>/prices` ([docs](https://api.tiingo.com/documentation)) | Free key; ~50 req/h, 1,000/day, 500 unique symbols/month (third-party; [Massive vs Tiingo](https://massive.com/compare/massive-vs-tiingo.md)) | Free; "Power" ~$30/mo for individuals (unverified, [review](https://daytradereview.com/tiingo-review)) | Closed. Individual plan = personal use; public redistribution not allowed (unverified; check tiingo.com/about/pricing) | Decades; Tiingo says it keeps delisted tickers (unverified) | 500-symbol cap fits ~200 + benchmarks | Low | **High** (best free EOD fit) |
| **Massive (ex-Polygon.io)** | EOD aggregates, splits/dividends/ticker-events reference endpoints | Free key, 5 calls/min, EOD only, 2 years history ([summary](https://apicostcalc.com/blog/polygon-massive-rebrand-api-pricing.html)); rebrand 2025-10-30 | Free → ~$29-79/mo (sources conflict) | Closed; personal/non-display on lower tiers (unverified) | 2 years on free; has `/v3/reference/splits` and ticker-change events | 5/min → 200 tickers ≈ 40 min/day; grouped-daily endpoint gives whole market in 1 call | Low-medium | **High** (grouped daily + corporate actions) |
| **Alpha Vantage** | EOD, adjusted, news sentiment | Free key, **25 req/day** ([official](https://alphavantage.co/premium)) | $49.99/mo (75/min) → $249.99 | Closed; terms restrict redistribution ([ToS](https://alphavantage.co/terms_of_service)) | 20+ yrs | 25/day is useless for 200 tickers | Low | Low |
| **Finnhub** | Quotes, company news, filings, (candles = premium) | Free key, 60/min ([pricing](https://finnhub.io/pricing)) | Free → paid per module | Closed; self-serve = "Personal Use"; display to others needs enterprise ([pricing](https://finnhub.io/pricing)) | News 1 yr on free (third-party) | Candles not free | Low | Medium (news, not prices) |
| **EODHD** | EOD global incl. Euronext | Free key, 20 calls/day ([limits](https://eodhd.com/financial-apis/api-limits)) | Free → ~€20/mo EOD (unverified) | Closed | Long; includes delisted on paid | Free = trial only | Low | Low (free) / Medium if paid (cheap global EOD incl. IWDA) |
| **Twelve Data** | EOD/intraday | Free key, 800 credits/day, 8/min ([pricing](https://twelvedata.com/pricing.md)) | Free → paid | Closed; free = "internal non-display usage only" ([pricing](https://twelvedata.com/pricing.md)) | | Non-display: no public charts | Low | Low-medium |
| **Nasdaq Data Link** | Mostly paid datasets now (e.g. Sharadar) | Key | Paid datasets | Closed | | Free WIKI prices dead since 2018 (from memory, unverified) | — | Low |
| **Alpaca market data** | IEX real-time free; historical SIP bars except last 15 min ([docs](https://docs.alpaca.markets/docs/about-market-data-api)) | Needs an Alpaca (paper) account | Free → $99/mo SIP | Closed; broker account = conflicts with "no broker" spirit (paper account only, but still a broker sign-up) | Years | IEX ≈ 2-3% of volume | Medium | Low-medium (owner decision) |
| **IEX Cloud** | — | **Shut down 2024-08-31** ([Alpha Vantage note](https://www.alphavantage.co/iexcloud_shutdown_analysis_and_migration/)) | — | — | — | — | — | Avoid |
| **Nasdaq Trader symbol directories** | `nasdaqlisted.txt`, `otherlisted.txt`: all listed symbols, test-issue and financial-status flags ([tested](https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt)) | No key | Free | Exchange-official; terms not checked in detail | **Overwritten daily → archive** | Financial Status flag (D=deficient, etc.) is a cheap delisting-risk signal | Low | **High** (universe + deficiency flag) |
| **SEC/FINRA** | No price data; FINRA daily short volume includes total volume (off-exchange reported only, see §5) | — | Free | Public | | Not a price source | — | — |

**IWDA (iShares Core MSCI World UCITS, Euronext Amsterdam `IWDA`, LSE `IWDA`/`SWDA`):** options: yfinance `IWDA.AS` (fragile, personal use), Tiingo (EU coverage unverified), EODHD free 20/day is enough for one ticker but is a trial tier ([limits](https://eodhd.com/financial-apis/api-limits)), iShares NAV history (iShares terms ban automated scraping on at least one terms page, [factor box terms](https://www.ishares.com/us/compliance/factor-box-terms)). Stooq `iwda.uk` was the classic free route but is now behind a JS wall (test). Practical: one call/day via EODHD free or yfinance; IWDA trades in EUR/USD — compare in one currency and document FX source (ECB reference rates, §8).

**Public display:** essentially every commercial vendor forbids redistributing raw prices; showing *our own portfolio returns and derived charts* is the common-sense line, but terms rarely say so explicitly (unverified for each). Keep raw price tables out of the public repo (add to `.gitignore`), publish only computed returns/NAV.

---

## 2. Corporate actions (reverse splits, delistings, deficiency notices, ticker changes, mergers/CVRs)

| Source | Contents / access | Key / cost | Terms | PIT | Value / notes |
|---|---|---|---|---|---|
| **Nasdaq Daily List** | Additions, deletions, symbol/name changes, splits (in dividends component) ([product page](https://nasdaqtrader.com/Trader.aspx?id=DailyListPD), [spec](https://m.nasdaqtrader.com/content/technicalSupport/specifications/dataproducts/dlcompletespec.pdf)) | **Paid subscription**; SEC filing lists $3,500/month for Daily List + fundamentals ([SR filing](https://www.sec.gov/files/rules/sro/nasdaq/2026/34-106034.pdf)) | Closed | Current month only | Too expensive; avoid. Free "daily list" pages on nasdaqtrader.com exist for symbol changes (unverified scope) |
| **Nasdaq Non-Compliant Companies list** | Daily list of companies out of compliance with continued listing rules; added ~5 business days after notice ([list](https://listingcenter.nasdaqomx.com/NonCompliantCompanyList.aspx)) | Free web page | Scraping terms unverified | **Current state only → archive daily** | **High**: bid-price (<$1) deficiency → reverse-split/dilution risk |
| **Nasdaq "Issues Pending Suspension or Delisting"** ([page](https://www.nasdaq.com/market-activity/stocks/issuers-pending-suspension-delisting)) | Web page | Free | nasdaq.com has bot protection (unverified) | Overwritten → archive | High for exits |
| **SEC 8-K items** 3.01 (delisting notice), 3.03, 5.03 (charter amendment, reverse split), 1.01/2.01 (M&A), and S-4/DEFM14A/SC TO-T (tender offers, CVRs) | EDGAR full-text search + submissions JSON; requires declared User-Agent with contact, 10 req/s ([SEC](https://www.sec.gov/os/accessing-edgar-data)) | Free | US government, public domain; attribution not required | Filings are immutable, timestamped → excellent PIT | **High**; covered in the SEC catalogue (other report) |
| **Massive/Polygon reference splits + ticker events** | See §1 | Free key | Closed | Kept | Medium: easiest machine-readable split feed |
| **Nasdaq Trader symbol directory `Financial Status` column** | D/E/Q/H/G/K codes (deficient, delinquent, bankrupt...) | Free | Exchange-official | Overwritten → archive | High, trivial |

Trap: **reverse splits in small biotech are common**; vendor "adjusted close" is rewritten retroactively after each split, so a stored adjusted series and a fresh download will disagree. Store raw close + a split table and adjust ourselves.

---

## 3. Universe definition

| Source | Access | Terms / PIT | Value |
|---|---|---|---|
| **SPDR XBI daily holdings xlsx** | `ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-xbi.xlsx` (new URL, test above) | SSGA terms: copyright, copying restricted (US page not read; HK version [here](https://www.ssga.com/hk/en/footer/terms-and-conditions)); **overwritten daily → archive** | **High**: ~140 names, equal-weight-ish small/mid biotech = core universe. Note XBI is no longer pure equal-weight since 2024-06 (liquidity-capped) ([BioCentury](https://www.biocentury.com/article/652965/biotech-losing-its-xbi-barometer)) |
| **iShares IBB holdings CSV** | `ishares.com/us/products/239699/.../1467271812596.ajax?fileType=csv...` — GET returned HTML today | iShares terms (on at least one page) prohibit scraping/bots ([factor box terms](https://www.ishares.com/us/compliance/factor-box-terms)); overwritten daily | Medium; manual monthly download is the clean route |
| **Nasdaq Biotechnology Index (NBI)** | Methodology PDF ([NBI](https://indexes.NASDAQomx.com/docs/methodology_NBI.pdf)); annual December reconstitution, announced early December, effective after 3rd Friday of December | Membership list via IBB holdings or Nasdaq announcement | Medium |
| **SEC EDGAR SIC codes 2834/2835/2836/8731** | Company submissions JSON per CIK; SIC list browse | Public domain | **High**: survivorship-free superset (includes de-listed filers) |
| **Market cap = XBRL `dei:EntityCommonStockSharesOutstanding` × price** | SEC companyfacts/frames API | Public domain; shares figure is as-of cover date (lags dilution!) | High, but shares lag ATM offerings by up to a quarter |
| **Nasdaq Trader symbol directories** | §1 | Archive daily | High (listing status, ETF flag) |

Recommended: universe = union(XBI holdings, NBI members, SIC-coded EDGAR filers on Nasdaq/NYSE) filtered by our own cap/volume floor, **frozen with a timestamp at start** and re-run monthly with snapshots kept.

---

## 4. Options / implied volatility ("what is priced in")

| Source | Access | Cost | Terms | Verdict |
|---|---|---|---|---|
| Cboe delayed quotes pages / JSON | `cboe.com/delayed_quotes/<T>/quote_table`; JSON on cdn.cboe.com is undocumented ([apis.io note](https://apis.io/providers/cboe/)), Cloudflare-protected (test) | Free web | Cboe market-data policies restrict automated use (garbled snippet, unverified) ([policy](https://cdn.cboe.com/resources/membership/Market_Data_Policies_Redlined.pdf)) | Avoid automation |
| Yahoo option chains via yfinance | `Ticker.option_chain()` | Free | Personal use only, fragile | **Only realistic free option**: once-daily snapshot of the nearest expiry straddle for the ~20-40 names with a catalyst in the next 60 days. Archive it (Yahoo keeps **no** option history) |
| OCC volume / open interest | Batch URL downloads for volume statistics ([OCC batch](https://prd-web.theocc.com/market-data/market-data-reports/other-market-data-info/batch-processing)) | Free | Terms unverified | Low: volume/OI, no IV |
| Massive options, Tradier, ORATS, IVolatility, Cboe DataShop/LiveVol | Paid APIs ([Cboe LiveVol](https://ww2.cboe.com/market_data_services/us/options)) | Massive options ~$29+/mo, ORATS ~$99+/mo (from memory, unverified) | Closed | Paid route if owner wants proper IV history |

Realistic verdict: implied move matters for "what is priced in" around PDUFA/readouts, but many $300M-$1B biotechs have thin or no listed options. Free = yfinance straddle snapshot (ATM call+put mid ÷ price), flagged as approximate, archived daily. No free IV history.

---

## 5. Short interest, short volume, FTD, borrow

| Source | Contents / access | Key / cost | Terms | Freshness / PIT | Value |
|---|---|---|---|---|---|
| **FINRA Equity Short Interest** | Twice-monthly positions, all exchange-listed + OTC; online 1 rolling year, archive download ([FINRA](https://www.finra.org/finra-data/browse-catalog/equity-short-interest), [file API guide](https://WWW.FINRA.ORG/sites/default/files/Equity_Short_Interest_Data_File_Download_API.pdf)); CDN pattern `cdn.finra.org/equity/otcmarket/biweekly/shrt{YYYYMMDD}.csv` (third-party, unverified) | Free, no key for files | FINRA Equity Data terms: non-commercial personal use, attribute FINRA as source ([Equity terms](https://developer.finra.org/sites/default/files/2022-12/Developer%20API%20-%20Specific%20Terms%20-%20Equity%20Data%20%2812-2022%29%5B10%5D.pdf)) | ~1-2 week publication lag; history kept | **High** for small biotech (squeeze/bear signal, days-to-cover) |
| **FINRA Reg SHO daily short-sale volume** | `cdn.finra.org/equity/regsho/daily/CNMSshvol<YYYYMMDD>.txt` (**tested, works**) | Free | Same FINRA attribution | T+1; archives kept | Low-medium: it is *off-exchange short volume*, routinely misread as short interest. Noise |
| **FINRA Query API (developer.finra.org)** | Equity datasets; equity APIs reportedly do not need auth ([support](https://developer.finra.org/support)) | Free | Non-commercial personal use + attribution | | Medium (cleaner than files) |
| **SEC fails-to-deliver** | Twice monthly zip; first half posted end of month, second half ~15th of next ([SEC FTD](https://www.sec.gov/data/foiadocsfailsdatahtm)) | Free; contact User-Agent | Public domain | Aggregate net balance, 2-6 wk lag | Low: noise for our use |
| **Reg SHO threshold lists** (Nasdaq Trader, NYSE) | Daily text files | Free | Exchange | Overwritten (archives exist on nasdaqtrader, unverified) | Low |
| **Interactive Brokers stock-loan FTP** | `ftp2.interactivebrokers.com`, user `shortstock`, no password; symbol, fee/rebate rate, shares available ([IBKR KB](https://ibkb.interactivebrokers.com/article/2024)) | Free, **no account needed** for FTP | IBKR terms on reuse not found (unverified) | **Overwritten intraday → archive** | **Medium-high**: borrow fee is the best free proxy for crowded shorts |
| iBorrowDesk | Web front-end on IBKR data | Free | — | Status 2026 **unverified** (no results) | Use IBKR FTP directly |
| ORTEX, S3 Partners, Fintel | Closed, paid (prices unverified) | | | | Skip for now |

---

## 6. Index changes

| Index | Rule / schedule | Where announced (open) |
|---|---|---|
| **Russell US (R2000 etc.)** | **Verified: semi-annual from 2026.** June recon + first December recon: rank day 2026-10-30, effective after close 2026-12-11, new indexes 2026-12-14 ([LSEG press release 2026-09-01](https://www.lseg.com/en/media-centre/press-releases/ftse-russell/2026/ftse-russell-announces-december-2026-russell-us-indexes-reconstitution-schedule), [move to semi-annual](https://lseg.com/en/ftse-russell/research/russell-us-indexes-move-to-semi-annual-reconstitution)) | Preliminary lists on FTSE Russell site (free registration may be needed for files, unverified). **December 2026 recon falls inside our live window — a known flow event for small biotech.** |
| **S&P Biotechnology Select Industry (XBI)** | Quarterly rebalance; eligibility + float-adjusted liquidity ratio; equal weight capped by 3-month median traded value basket liquidity ([methodology](https://spglobal.com/spdji/es/documents/methodologies/methodology-sp-select-industry-indices.pdf)) | S&P DJI index announcements (free web, registration for alerts) |
| **Nasdaq Biotechnology (NBI)** | Annual, December; data as of end Oct / shares end Nov; effective after 3rd Friday of Dec ([NBI methodology](https://indexes.NASDAQomx.com/docs/methodology_NBI.pdf)) | Nasdaq GlobeNewswire press release early December ([example](https://mondovisione.com/news/annual-changes-to-the-nasdaq-biotechnology-index-7-20201212)) |
| MSCI | Quarterly reviews (Feb/May/Aug/Nov) — from memory, unverified | msci.com press releases |

Value: medium. Index adds/deletes are documented price-pressure events; useful as a calendar input, cheap (a handful of press releases per year).

---

## 7. ETF holdings and 13F

| Source | Access | Terms | PIT | Value |
|---|---|---|---|---|
| **ARK ARKG daily holdings CSV** | `assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_GENOMIC_REVOLUTION_ETF_ARKG_HOLDINGS.csv` (**tested**); file dated next trading day ([ARK help](https://helpcenter.ark-funds.com/can-you-explain-the-date-listed-on-the-ark-etf-holdings-documents)) | ARK site terms not read (unverified) | **Verified: ARK keeps no historical trade archive** ([ARK help](https://helpcenter.ark-funds.com/do-you-share-historical-trades)) → archive from day 1 | Medium: benchmark composition, not alpha |
| ARK daily trade e-mails | Sign-up e-mail ([ARK](https://ark-funds.com/trade-notifications)) — needs e-mail address; excludes creations/redemptions | | Not kept by ARK | Low; diff the daily CSVs instead (no sign-up) |
| SPDR XBI, iShares IBB | §3 | §3 | Overwritten → archive | High (XBI) |
| Other biotech ETFs: SBIO (ALPS Medical Breakthroughs — small/mid clinical-stage, very relevant), BBH (VanEck, cap-weighted large), IDNA, GNOM | Issuer sites (terms unverified) | | Overwritten | SBIO medium (its rule = "has a drug in phase 2/3", a neat universe check); others low |
| **SEC Form 13F data sets** | Quarterly ZIP of tab-delimited files from 13F XML, since 2013; published in Feb/May/Aug/Nov ([SEC 13F data sets](https://www.sec.gov/dera/data/form-13f), [readme](https://sec.gov/files/form_13f_readme.pdf)) | Public domain | "As filed", amendments included, redundancies possible | **High as benchmark**, low as signal (45-day lag + quarterly) |

Biotech specialist 13F filers (names from domain knowledge; **CIKs must be verified** on EDGAR before use): RA Capital, Baker Bros. Advisors, Perceptive Advisors, OrbiMed, Deerfield, BVF (Biotechnology Value Fund), EcoR1, Boxer Capital, Avoro Capital, RTW Investments, Farallon (generalist), plus commonly cited Cormorant, Venrock Healthcare Capital Partners, Commodore, Logos, Janus Henderson biotech team (unverified list). Trap: 13F covers long US equity + options only, no shorts, no non-US listings, and filers can request confidential treatment.

---

## 8. Macro and policy

| Source | Access | Key | Terms | Value |
|---|---|---|---|---|
| **US Treasury daily par yield curve** | CSV/XML, key-less (**tested**) | No | US government | **High**, trivial (rates are the main macro driver of XBI) |
| **FRED API** | `api.stlouisfed.org/fred/...` | **Free key required** ([terms](https://fred.stlouisfed.org/docs/api/terms_of_use.html)) | Some series third-party copyrighted; serving via API grants no reuse right ([terms](https://fred.stlouisfed.org/docs/api/terms_of_use.html)) | Medium (Treasury file covers most needs; FRED adds credit spreads, VIX — VIX is Cboe-copyrighted) |
| ECB Data Portal | SDMX REST, key-less (from memory, unverified) | No | ECB reuse policy allows with attribution (unverified) | Low-medium (EUR/USD for IWDA comparison) |
| Fed FOMC calendar | federalreserve.gov static page | No | Public | Medium (calendar input; 8 meetings/yr) |
| **Congress.gov API** | Free api.data.gov key, ~5,000 req/h ([LoC GitHub](https://www.github.com/LibraryOfCongress/api.congress.gov)) | Yes | Public | Low-medium |
| **Federal Register API** | No key ([guide](https://www.vaquill.ai/blog/federal-register-api-python-search-rules-and-notices)) | No | Public | Medium: catches tariff proclamations, CMS/HHS drug-pricing rules |
| regulations.gov API | api.data.gov key | Yes | Public | Low |

**Rate sensitivity evidence:** no peer-reviewed XBI-specific paper found in this session. The best-established framework is *implied equity duration* (Dechow, Sloan & Soliman 2004, [Review of Accounting Studies PDF](https://www.bus.umich.edu/facultyresearch/researchcenters/centers/tozzi/duration.pdf); follow-up [Dechow et al. 2021, J. Accounting Research](https://econpapers.repec.org/RePEc:bla:joares:v:59:y:2021:i:1:p:243-281)): firms whose value sits in distant cash flows (pre-revenue biotech is the extreme case) react more to discount-rate changes. Recommend we measure it ourselves (rolling XBI beta to 10-yr yield changes) as an event-study item rather than cite commentary.

**Policy status as of 2026-11-15 (verify before relying):**
- **BIOSECURE Act: law.** Signed 2025-12-18 as Sec. 851 of the FY2026 NDAA; OMB list of biotech companies of concern due by Dec 2026; guidance ~June 2027; 5-year safe harbor for existing contracts ([Akin](https://www.akingump.com/en/insights/alerts/biosecure-act-becomes-law), [Arnold & Porter](https://www.arnoldporter.com/en/perspectives/advisories/2025/12/the-biosecure-act-becomes-law-in-the-united-states)). **The OMB list due ~Dec 2026 is a live-window event** (WuXi-dependent small biotechs).
- **Section 232 pharma tariffs:** proclamation 2026-04-02: 100% on patented drugs; 20% with onshoring plans; 10% UK, 15% EU/Japan/Korea/Switzerland; generics, biosimilars and **orphan drugs excluded**; effective for all importers 2026-09-29; 0% for companies with MFN deals through 2029-01-20 ([Ropes & Gray](https://www.ropesgray.com/en/insights/alerts/2026/04/100-on-brand-us-imposes-new-tariffs-and-key-exemptions-on-patented-pharmaceuticals), [Thompson Hine](https://www.thompsonhinesmartrade.com/2026/04/president-trump-announces-section-232-tariffs-on-pharmaceuticals-and-active-pharmaceutical-ingredients/)).
- **MFN drug pricing:** EO 14297 (2025-05-12); White House claims 26 large drugmakers signed deals, extended to all Medicaid programs (Sept 2026) ([White House](https://www.whitehouse.gov/releases/2026/09/president-trump-extends-most-favored-nation-pricing-to-every-medicaid-program-in-america/); administration claim). Small biotechs mostly not direct parties.
- **NIH:** FY2026 = $48.7B (Congress raised it); FY2027 request = −$5B and 5 institutes eliminated; final FY2027 appropriation not found ([Applied Clinical Trials](https://www.appliedclinicaltrialsonline.com/view/white-house-5-billion-nih-cut-fy2027-budget), [Axios](https://www.axios.com/2026/04/02/research-advocates-nih-budget-fight?stream=top)).
- IRA changes: not researched in this session (unverified).

Cheap way to follow: Federal Register API saved searches (agency = HHS/FDA/CMS/USTR, term "pharmaceutical"), FDA press-release RSS, Congress.gov bill status for a short watch-list. An LLM screens these weekly — policy moves the sector, rarely one small cap.

---

## 9. News, sentiment, social

| Source | Access / limits | Cost | Terms (automated personal / public display) | PIT | Value for small biotech |
|---|---|---|---|---|---|
| **Company press releases + 8-K Ex-99.1** | EDGAR (immutable, timestamped); company IR RSS (most IR sites run on Q4/Notified, have RSS, unverified per company) | Free | Public filings fine; IR sites: personal use | EDGAR = perfect PIT | **High**: the primary news source for this fund |
| **GDELT DOC 2.0 / GKG** | `api.gdeltproject.org/api/v2/doc/doc`; max 250 records, artlist limited to last ~3 months, 1 req/5 s (tested: throttled) ([GDELT blog](https://blog.gdeltproject.org/doc-2-0-updates-1-5-year-searching-and-updated-mobile-interface/)) | Free | Unlimited use incl. commercial, **citation + link required** ([About](https://www.gdeltproject.org/about.html)) | DOC window rolls → archive what we use | Low-medium: good for macro/policy tone, thin for $500M biotechs |
| **Google News RSS** | `news.google.com/rss/search?q=...` | Free | Google ToS: no automated querying in general (unverified for RSS); fragile | Rolling | Medium as discovery, but grey; use sparingly |
| **Trade press RSS**: Endpoints News, FierceBiotech, STAT, BioSpace, BioPharma Dive, Evaluate Vantage/ApexOnco | Public RSS feeds exist for most (unverified per feed); STAT+ and Endpoints partly paywalled | Free headlines | RSS = personal reading allowed; no republishing full text (standard) | Rolling → store headline+link+timestamp | **High** per effort: headlines + link only, LLM triage |
| **NewsAPI.org** | Free dev: 100 req/day, 24 h delay, **dev environment only, not production** ([pricing](https://newsapi.org/pricing)) | Business $449/mo | Free tier forbidden for our live use | | Avoid |
| **GNews** | 100 req/day, 10 articles/req ([gnews.io](https://gnews.io)) | Paid from ~€50/mo (unverified) | Free = non-commercial/dev | | Low |
| **Marketaux** | 100 req/day, 3 articles/req ([pricing](https://marketaux.com/pricing)) | Paid tiers | Terms unverified | | Low-medium (entity-tagged by ticker) |
| **Finnhub company news** | Free 60/min, per ticker ([pricing](https://finnhub.io/pricing)) | Free | Personal use only | 1 yr | Medium: easy per-ticker aggregator |
| **Alpha Vantage NEWS_SENTIMENT** | 25 req/day total | Free | Personal | | Low |
| Benzinga | Paid API | Closed, paid (price unverified) | | | Skip |
| **Reddit** | Since **2025-11-11 "Responsible Builder Policy": new API access needs approval**; anecdotal denials ([r/redditdev thread mirror](https://r.datuan.dev/r/redditdev/comments/1oug31u/introducing_the_responsible_builder_policy_new/noc31sg)); free tier 100 QPM non-commercial, no AI training (third-party, [summary](https://data365.co/blog/reddit-api-pricing)); official wiki returned 403 to me | Free if approved | Non-commercial only; **AI/LLM use of content restricted** (unverified exact clause) — an LLM agent reading Reddit is a grey zone | Rolling | Low: r/Biotechplays is retail noise; skip v1 |
| **StockTwits** | Official API restricted/closed to new developers (secondary evidence, [OneUp 2024](https://help.oneupapp.io/en-us/article/does-oneup-support-stocktwits-1fxjlx0/)) | — | — | — | Avoid |
| **X/Twitter API** | Free tier ended for new devs 2026-02; pay-per-use ~$0.005 per post read, caps ~2-3M reads/mo (third-party, conflicting: [Open Terms Archive](https://opentermsarchive.org/en/memos/x-replaces-its-dollar200-entry-level-api-plan-with-a-pay-per-use-model/), [data365](https://data365.co/guides/twitter-api-limitations-and-pricing)) | Following ~100 biotech accounts × ~20 posts/day ≈ 60k reads/mo ≈ **$300/mo** (my estimate) | Closed | | Biotech fintwit matters, but cost and terms rule it out for a no-cost v1. Scraping = ToS breach. **Verdict: skip** |
| **Bluesky** | Firehose / Jetstream, no auth ([atproto docs](https://atproto.com/guides/streaming-data), [Jetstream](https://docs.bsky.app/blog/jetstream)); or per-account `app.bsky.feed.getAuthorFeed` | Free | Open protocol; Bluesky ToS on automated access not read (unverified) | Archive ourselves | Low-medium: some biotech scientists/journalists moved there; cheap to follow a list of ~50 accounts |
| **Short-seller reports** | Hindenburg **closed** (announced 2025-01-15) ([Al Jazeera](https://www.aljazeera.com/economy/2025/1/16/muckraking-financial-firm-hindenburg-research-to-disband-founder-says)); Muddy Waters, Citron, Scorpion, Culper, Fuzzy Panda, Kerrisdale: own websites/X, RSS availability unverified | Free | Personal reading | | Medium as *risk* flag (a report = sudden −20-50%); detect via price gap + news search, not a feed |
| **M&A / licensing** | 8-K items 1.01/2.01, press releases (open); Evaluate, BioCentury, DealForma, Cortellis (closed, $$$$) | | | | High via 8-K; closed DBs skip |
| China out-licensing | Company 8-Ks/PRs, HKEX filings (open, `hkexnews.hk`), trade press | Free | | | Medium (a 2025-26 dominant deal theme; LLM tags deals with a China licensor) |

---

## 10. Alternative data (be critical — mostly noise for this fund)

| Source | Access / terms | PIT | Verdict |
|---|---|---|---|
| **Job postings (Greenhouse/Lever public JSON)** | `boards-api.greenhouse.io/v1/boards/{token}/jobs` (no auth for GET), `api.lever.co/v0/postings/{site}?mode=json` (no key) ([summary](https://dev.to/zsevic/integration-with-greenhouse-public-jobs-api-1lj3)); official docs not read. Workday = undocumented, skip. LinkedIn = no scraping | **Current only → archive weekly** | Medium-low: hiring commercial/launch staff before PDUFA, or layoffs, are real signals, but small biotechs post few jobs. Cheap; maybe v2 |
| **WARN notices** | State sites; open-source scraper `warn-scraper` (Big Local News, Stanford) ([docs](https://warn-scraper.readthedocs.io/)) | Archive | Low-medium: layoffs usually also in 8-K/PR; WARN can be earlier (MA, CA, NJ biotech hubs) |
| Web traffic (Similarweb closed); Tranco, Cloudflare Radar | Tranco = top-1M domains only | | Low: small biotech sites are not in top lists → skip |
| **Wikipedia pageviews** | Key-less, contact UA required ([policy](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/access-policy.html)); tested works | Kept by provider | Low: few small biotechs have articles; maybe attention spikes |
| **Google Trends** | Official API is **alpha, application-only** since 2025-07-24 ([Google](https://developers.google.com/search/blog/2025/07/trends-api)); pytrends = unofficial scraping, ToS grey, frequent 429s | | Low; skip |
| KOL activity / **CMS Open Payments** | Annual (June) public dataset, open API (from memory; unverified) | Kept | Low: annual lag; useful only for case library |
| **ClinicalTrials.gov site counts / status changes** | CT.gov API v2 (covered in clinical report) — **record history exists** but snapshot our own daily diffs | Versions kept by CT.gov | **High** (in clinical catalogue): site activations, enrollment, completion-date slips |
| FDA calendar FOIA logs | FOIA logs published, lagged | | Low |
| USAspending / BARDA / NIH RePORTER | Open APIs, key-less (unverified) | Kept | Low-medium (BARDA contracts matter for a few names) |
| Lobbying disclosures (Senate LDA API) | Open | | Low |
| **CourtListener / RECAP** | REST v4, free token; free limits lowered 2026-05 to ~5/min, 125/day ([Free Law Project](https://free.law/2026/05/07/api-included-in-memberships/), via third-party summary) | Kept | Medium-low: patent (Paragraph IV / IPR) and securities class actions; securities suits are lagging, patent suits matter for a few. Docket alerts on ~20 holdings fits the limit |
| GitHub activity for AI-biotechs | GitHub API (token) | | Low: noise |
| Wikipedia edits | Open | | Low |
| App store / prescription data (IQVIA, Symphony) | Closed, expensive | | Skip; for launches use quarterly 10-Q revenue |
| **USPTO trademarks** (brand names before approval) | USPTO TSDR / trademark search; TSDR API needs a key (unverified) | Kept | Low, fun: new brand-name filings hint at launch prep, but big pharma floods filings |
| Import records (Panjiva/ImportGenius) | Closed, paid | | Skip |
| Glassdoor | Closed, ToS forbids scraping | | Skip |
| **IPO lock-up / insider** | Lock-up dates from S-1/424B (180 days typical); Form 4 insider trades (EDGAR) | Immutable filings | **Medium-high**: lock-up expiry and insider selling are well-documented small-cap price events; computable from EDGAR for free |
| Follow-on / ATM offering detection | 424B5 prospectus supplements, S-3 shelf filings on EDGAR | Immutable | **High**: dilution is the #1 small-biotech trap; detect same day |

---

## 11. Ranked top-8 by value per effort

1. **SEC EDGAR filings feed** (8-K items, 424B5/S-3 offerings, Form 4, S-1 lock-ups) — free, public domain, perfect PIT, highest signal for small biotech. (Details in the SEC catalogue.)
2. **Tiingo free EOD** (or Massive free grouped-daily) + own raw-close archive — needed anyway; 500-symbol cap fits.
3. **US Treasury yield CSV** — key-less, one call/day, main macro driver.
4. **Nasdaq Trader symbol directory + Nasdaq Non-Compliant list** (daily archived) — trivial, flags reverse-split/delisting risk.
5. **SPDR XBI daily holdings + ARKG CSV** (daily archived) — universe + benchmark composition; history not kept by issuers.
6. **FINRA short interest (bi-monthly) + IBKR stock-loan FTP (daily archived)** — free, crowded-short and squeeze context.
7. **Trade-press RSS headlines + company IR RSS** (headline+link+timestamp only) — cheap LLM triage.
8. **yfinance option-chain straddle snapshot** for names with a catalyst <60 days (daily archived) — the only free "priced-in" proxy; personal use, fragile.

Runners-up: SEC 13F data sets (benchmark only, quarterly), Federal Register API (policy), CourtListener alerts, Greenhouse/Lever jobs (v2).

## 12. Start archiving on day 1 (history not kept by provider, or overwritten)

- XBI (SSGA), IBB (iShares, manual), ARKG (ARK — verified no history), SBIO holdings files — daily.
- Nasdaq Trader `nasdaqlisted.txt` / `otherlisted.txt` — daily.
- Nasdaq Non-Compliant Companies list and Pending Suspension/Delisting page — daily.
- IBKR stock-loan FTP file (fee + availability) — daily (intraday not needed).
- Option chain snapshots (Yahoo) for catalyst names — daily; nobody gives free IV history.
- Raw unadjusted close/volume per ticker as fetched (vendors rewrite adjusted history after splits) — daily.
- Our universe membership snapshot (with criteria and timestamp) — monthly.
- News/RSS items as seen (headline, link, fetch timestamp) — feeds roll over; also needed for the "data the agent saw" log rule.
- GDELT DOC results we use (rolling ~3-month window).
- Job-board snapshots (if used) — weekly.
- Nice-to-have: FINRA daily short volume (archived by FINRA anyway, low priority).

## 13. Sources to avoid (and why)

- **Stooq** — automated CSV now blocked by a JS proof-of-work wall (tested 2026-11-15); no published terms.
- **NewsAPI.org free** — terms forbid production use; Business is $449/mo.
- **X/Twitter API** — no free tier for new developers since 2026-02; realistic monitoring ≈ $300/mo; scraping breaches ToS.
- **StockTwits** — no open developer access.
- **Reddit** — approval-gated since 2025-11, non-commercial, AI-use restrictions; low signal anyway.
- **pytrends / Google Trends scraping** — ToS grey, unreliable; official API is closed alpha.
- **Cboe delayed-quote JSON** — undocumented, bot-protected, market-data policy restricts automation.
- **Nasdaq Daily List subscription** — ~$3,500/month.
- **iShares automated scraping** — terms prohibit bots (at least on one page); download IBB manually or use NBI announcements.
- **IEX Cloud** — dead since 2024-08-31.
- **Alpha Vantage / EODHD / Twelve Data free tiers** as primary — 25/day, 20/day, non-display terms.
- Closed alt-data (Similarweb, IQVIA, ORTEX, S3, Evaluate, Glassdoor, LinkedIn) — cost/terms.

## 14. Points needing the owner's decision

1. **Primary EOD price source:** Tiingo free (key, personal use) vs Massive free (key, 2-yr history, 5/min) vs a small paid plan (e.g. EODHD or Tiingo Power ~$20-30/mo) for delisted history and fewer failures. Recommendation: Tiingo free + Massive free as cross-check; revisit after pilot.
2. **Public repo rule:** publish only our own computed returns/NAV and charts, never raw vendor price/holdings tables (keep in a gitignored data folder or private backup). Needs an explicit ADR.
3. **Signing up for free API keys** (Tiingo, Massive, FRED, Finnhub, Congress.gov, CourtListener): each needs an account with e-mail — owner action.
4. **Alpaca paper account for data?** It is a broker sign-up even if paper-only; conflicts with the spirit of "no broker". Recommendation: don't.
5. **Social media:** accept that biotech fintwit (X) is out of reach for free; optionally follow a Bluesky list. Reddit only if owner wants to apply for access.
6. **Options implied move:** accept yfinance's grey "personal use" status for a daily straddle snapshot, or drop "priced-in" IV and use historical event-move statistics instead.
7. **User-Agent for SEC/Wikimedia:** these require contact info; decide on a project contact (GitHub repo URL / a dedicated project e-mail) rather than the owner's personal address.
8. **Archive storage and retention** for daily snapshots (size small: <50 MB/month estimated, unverified) — where to keep them.

## 15. Uncertain / not verified in this session

Tiingo exact free limits and delisted coverage; Massive free-tier terms on display; Yahoo's own terms wording; FINRA short-interest CDN filename; iBorrowDesk status; IBKR FTP reuse terms; SSGA US terms on automated download; Reddit official wiki text; Bluesky ToS on automated access; Cboe automation clause; OCC terms; MSCI schedule; ECB API key-less status; IRA changes; FDA commissioner confirmation status; final FY2027 NIH appropriation; 13F specialist-fund CIK list; trade-press RSS URLs per outlet; Open Payments/USAspending/USPTO API key requirements.
