# G. Forensics: early indicators before small/mid-cap biotech price events (research 2026-11-15)

Question (owner): *"Backtrace like forensics: for biotech companies in the past, were there early indicators that people missed, and what can we learn from that?"*

Method: web search and reading of secondary sources (news, trade press, company releases mirrored on newswires, court filings, paper abstracts). **No SEC EDGAR or NCBI E-utilities calls were made**, so wherever a filing is mentioned, the filing itself was **not read**; dates come from the secondary source linked. Price moves are as reported by the press (often intraday or pre-market; sources disagree by a few points). Anything not confirmed is marked **unverified**; anything from memory is labelled **from memory, unverified**.
Not investment advice. Hindsight warning up front: every case below was picked *after* its outcome was known. Treat the cases as a source of hypotheses, never as evidence that a signal works.

---

## 0. Answer first (short)

1. **The published evidence for "early tells" is thin and mostly old.** The one robust, replicated finding is that pre-event *price/options* activity leaks information (Rothenstein 2011; a 2000 J Investig Med study; Wu-Borochin-Golec 2024; Bohmann-Patel 2022). That says insiders know things; it does not give an outsider a usable signal before the move. Trial-design predictors (positive phase 2, genetic support, biomarker selection, sponsor track record) are real but modest, and are *priors*, not timing signals.
2. **"Good news travels fast" (late topline = bad) is not supported** by the one large dataset found (AppliedXL 2026: late readouts met endpoints 53% vs 55-56% for on-time/early). Off-hours releases *are* more often failures (27% vs 17%), but that tells you nothing *before* the release.
3. Across 14 hand-picked cases, **the signals that recur before bad outcomes and are rare before good ones** are: (a) a primary endpoint already missed and a bull case resting on post-hoc, subgroup or "corrected" analyses; (b) research-integrity problems at the founder/key-paper level; (c) a named manufacturing site with FDA observations before a PDUFA date; (d) effect size shrinking across successive data cuts of an open-label study. Lead times are long (weeks for (c), months to years for (a), (b), (d)), which is good for a 6-month fund only in the sense of *avoiding* names, not timing a short (the fund is long-only anyway).
4. **Signals that fail the false-alarm test** in this set: FDA advisory-committee cancellation (preceded two CRLs *and* the market treated it as good news), PDUFA extensions, a late-cycle "deficiencies" letter (Tricida failed, Axsome was approved a year later), short-seller reports (right on Nektar and Cassava years later; wrong or unresolved on Axsome, Capricor), high short interest (Madrigal rose >200% with >25% short interest), and a partner handing back rights (Cidara then became a $9.2B takeover).
5. Most "missed" signals were **not missed**: they were public, debated, and caused large price drops on the day they appeared. What the market got wrong, if anything, was the *second* step (e.g. buying the Cassava 2020 "reanalysis", or the Applied Therapeutics "formula correction").

---

## Part 1. Systematic evidence (published research)

Evidence strength scale: **R** = peer-reviewed and replicated; **S** = single peer-reviewed study; **P** = practitioner/vendor analysis (not peer-reviewed); **L** = lore/anecdote only; **N** = no evidence found.

### 1.1 Sponsor size: the "Feuerstein-Ratain rule"
- Claim: small companies (market cap ≤ ~$300M about four months before the result) essentially never succeed with an oncology phase 3. Named after TheStreet columnist Adam Feuerstein and oncologist Mark Ratain; a secondary source reports their 2011 analysis of ~58 phase 3 cancer drugs over 10 years: all 21 trials by companies under $300M failed; 21 of 27 by companies above $1B succeeded ([yypharm summary, Chinese](https://www.yypharm.com/?p=4897)). Columns updating it: [TheStreet update](https://www.thestreet.com/investing/stocks/the-feuerstein-ratain-rule-update-still-perfect-predicting-small-cap-cancer-drug-failure-12696926), ["mailbag: breaking the rule"](https://www.thestreet.com/investing/stocks/biotech-stock-mailbag-breaking-the-feuerstein-ratain-rule-medical-conferences-celgene-13084980), and a CTI BioPharma pacritinib case described as the first break "with an asterisk" (search summary; TheStreet pages returned 403, **not read**).
- The JNCI publication itself could **not be located** (possibly a letter/correspondence; the 59-trial 2000-2009 dataset matches Rothenstein et al. 2011, see 1.2) → **unverified provenance**. No independent, peer-reviewed replication found.
- Interpretation: the rule mostly says *the market already prices low odds* (a tiny cap at phase 3 means big pharma and specialists passed). Feuerstein himself framed it as a negative predictor only (search summary). For a long-only fund it is an exclusion screen, not alpha.
- Related: Addeo, Weiss & Gyawali, *JAMA Netw Open* 2019;2(5):e193684 ([link](https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2733181)): of 67 negative oncology phase 3 RCTs, 42% had no phase 2 at all; 8 proceeded despite a negative phase 2, and 4 of the 5 industry ones involved a drug bought/licensed from a company with cap < $2B.
- **Strength: L/P** (rule), **S** (no-phase-2 observation). False-alarm rate unknown; the rule's record comes from its authors' own tally.

### 1.2 Price run-ups before results (information leakage)
- Rothenstein, Tomlinson, Tannock, Detsky, *JNCI* 2011, doi:10.1093/jnci/djr338: 23 positive + 36 negative oncology phase 3 announcements (2000-2009) and 41 positive + 9 negative FDA decisions. 120 trading days before: +13.7% before positive trials vs −0.7% before negative (CI for +13.7% was −2.2% to 29.6%, i.e. not robust); post-hoc window comparison +9.4% vs −4.5% (P=.03); **no difference before FDA decisions** ([ScienceDaily](https://www.sciencedaily.com/releases/2011/09/110926165902.htm)).
- Earlier: *J Investig Med* 2000 (98 phase 3 products, 49 FDA panels): 120→3 days before, winners +27% vs losers −4% (P=0.0007), "indirect evidence that insider trading may be common" ([PubMed 10736971](https://pubmed.ncbi.nlm.nih.gov/10736971/); authors Overgaard, Detsky et al. **from memory, unverified**).
- Options: Wu, Borochin & Golec, *J Corp Finance* 84 (2024), 319 FDA advisory meetings 1997-2017: significant abnormal options trading before briefing documents are finalised and before meetings, strongest for **small** drug firms; calls before approvals, puts before rejections ([RePEc](https://ideas.repec.org/a/eee/corfin/v84y2024ics092911992300144x.html); [CLS Blue Sky summary](https://clsbluesky.law.columbia.edu/2022/01/11/informed-options-trading-before-fda-evaluations/): ~32% of meetings showed significant abnormal call volume, mostly short-dated OTM). Bohmann & Patel, *J Bus Fin Acc* 49(7-8) 2022: abnormal implied-volatility spreads and option activity before FDA announcements predict announcement-day returns, 21 years of data ([RePEc](https://ideas.repec.org/a/bla/jbfnac/v49y2022i7-8p1211-1236.html)).
- Event studies of the reaction itself: Singh et al., *PLoS ONE* 2022, 13,807 trial outcomes, biggest reactions for early-stage biotechs ([PMC9439234](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9439234/), already in C).
- **Strength: R** that leakage exists (several studies, different decades, stock and options). **Usefulness for us: low.** Effects are averages over noisy samples, need option data we don't have for free (E §4), and many small caps have no liquid options.

### 1.3 Predictors of phase 3 / approval failure knowable in advance (priors)
| Predictor | Evidence | Strength |
|---|---|---|
| Positive phase 2 (any design) | Monzon et al., *Eur J Cancer* 51:2501 (2015): 189 oncology phase 3 trials, 41.8% positive; positive phase 2 associated with positive phase 3 (p=0.03); **randomised phase 2 not better than single-arm** at predicting; endpoint, sponsor, sample size, population similarity *not* predictive ([McMaster record](https://experts.mcmaster.ca/display/publication1536798)) | S |
| No phase 2 at all | Addeo 2019 above (42% of negative ph3 had none) | S (descriptive, no controls) |
| Base rates by area/phase | Wong, Siah & Lo, *Biostatistics* 20(2):273 (2019): 406,038 trial entries, 21,143 compounds 2000-2015; overall POS ~13.8%, oncology 3.4% ([MIT](https://dspace.mit.edu/handle/1721.1/128480); [ACSH summary](https://acsh.org/news/2020/06/11/clinical-trial-success-rates-phase-and-therapeutic-area-14845)). Hay et al., *Nat Biotechnol* 32:40 (2014), 7,300+ paths, 2003-2011 ([PubMed](https://pubmed.ncbi.nlm.nih.gov/24406927/)). BIO/Informa/QLS 2011-2020: LOA from phase 1 7.9%, phase 2 transition 28.9%, biomarker-selected programmes ~2x LOA ([BIO](https://www.bio.org/clinical-development-success-rates-and-contributing-factors-2011-2020); figures via search summary) | R (consistent across datasets) |
| ML on trial features | Lo, Siah & Wong, *Harvard Data Sci Rev* 2019: AUC 0.78 (phase 2→approval), 0.81 (phase 3→approval); top features: trial outcome, status, accrual rate, duration, prior approval elsewhere, **sponsor track record** ([MIT CancerX](https://cancerx.mit.edu/machine-learning-with-statistical-imputation-for-predicting-drug-approvals); figures via search summary) | S |
| Human genetic support | Nelson 2015, Minikel 2024: ~2.6x POS (in F §11) | R |
| Primary-outcome switching / enrolment cuts in the registry | Non-peer-reviewed preprint: cutting enrolment targets and changing primary outcomes predicted later termination; completion-date slips (61% of trials) did not (Research Square, Oct 2026, cited in C §4, **not read here**) | P |
| Spin in reports | Boutron et al., *JAMA* 2010: 72 RCTs with non-significant primary outcome; spin in 58% of abstract conclusions ([summary](https://www.globalfamilydoctor.com/Resources/A-Ztopiclisting/JournalWatch/Howmuchspinistherewithnonsignificantresults63.aspx)). Yavchitz et al., *PLoS Med* 2012: spin in 47% of press releases, mostly inherited from the abstract ([DOAJ](https://doaj.org/article/b8a989a7404a4814acea08d48434b53e)) | R that spin is common; **N** on spin → later failure or returns |

### 1.4 Timing tells
- **Late topline vs promised date ("good news travels fast")**: AppliedXL, *The Readout Gap* (July 2026; vendor, not peer-reviewed): 681 trials with dated guidance; 58% missed the promised window, late misses ~2x early ones; **early 56% / on-time 55% / late 53% met the endpoint → "within noise"** ([AppliedXL](https://appliedxl.com/research/readout-gap)). Caveat: abandoned trials never resolve and skew to failure, so this is a floor. Anecdotes of very long silences before bad news exist (CEL-SCI, Northwest Bio: [STAT](https://www.statnews.com/2021/05/05/the-long-wait-for-cel-sci-to-finally-admit-its-cancer-drug-doesnt-work/), [STAT](https://www.statnews.com/2021/10/06/northwest-bio-marks-ignominious-anniversary-of-brain-tumor-study-delay-with-silence/)). **Strength: P against the hypothesis for ordinary delays; L for extreme silences.**
- **Off-hours release**: same AppliedXL report, 2,262 trials: after-close/weekend results failed 27% vs 17% in market hours (χ²=26). **P.** Zero lead time: it is a property of the announcement itself.
- **Friday/after-close general literature** (DellaVigna & Pollet, J Finance 2009, earnings: **from memory, unverified**); no biotech-specific peer-reviewed study found. **N** for biotech.
- **Disclosure deadlines**: most results miss the 1-year CT.gov deadline; firms in competitive markets disclose less on time ([HEC](https://www.hec.edu/en/what-influences-pharmaceutical-companies-disclose-clinical-trial-results-or-not), [UCLA Anderson](https://www.anderson-review.ucla.edu/mandated-disclosure-of-clinical-trials-ignored-especially-for-competitive-drugs)). Not a returns study.

### 1.5 Financing and ownership tells
Already reviewed in D §4 (insider buys: Cohen-Malloy-Pomorski 2012, strong in general, thin in biotech; going-concern drift: Kausar et al. 2009, moderate, but 36% of life-science firms carry one; ATMs: Billett et al. 2019; 13F specialist ownership: vendor-only). Additions here:
- Insider **sales** before bad news: case reports only (Seres, Juno via STAT, [BioSpace](https://www.biospace.com/how-biotech-execs-profit-from-legal-insider-trades)); a Stanford analysis of 10b5-1 trades found sales clustered before "valuable" news (search summary, **not read**). **L/S.**
- **Activist short reports**: cross-industry research (e.g. 351 reports 1996-2018, response behaviour vs returns; [LBS paper PDF](https://lbsresearch.london.edu/id/eprint/1699/1/1475-679X.12356.pdf)); a secondary summary of 825 reports (2009-2016) claims >20% average decline over four years (**unverified**, blog repost). **No biotech-specific study found.** Bloomberg notes biotech shorts are often right on thesis but wrong on timing ([BloombergQuint](https://www.bloombergquint.com/markets/2017/11/16/biotech-short-sellers-need-to-watch-for-more-than-bad-trials)). **S (general), N (biotech).**
- **Short interest predicting trial failure**: only anecdotes (Catabasis, Gossamer; [Schaeffer's](https://www.schaeffersresearch.com/content/news/2016/06/08/drug-data-deals-a-blow-to-catabasis-pharmaceuticals-inc-catb)). **N.**

### 1.6 Regulatory tells
- **Advisory-committee votes vs FDA action**: 2008-2015, 22% of FDA actions discordant with the committee, 75% of discordance in the restrictive direction (Milbank Q 2019; [summary](https://pink.citeline.com/PS147536/Advisory-Committee-Disagreement-With-US-FDA-On-Approval-Decisions-An-Increasingly-Rare-Event)); 2010-2021, 88% alignment (262/298) ([JAMA Health Forum](https://jamanetwork.com/journals/jama-health-forum/fullarticle/2807050)). **R.** But since 2025 adcomms are rare (C §6), so this tool has fewer events.
- **CRL reasons**: CMC/facility problems are the most common CRL reason (F §1, F §4). **P/S (FDA-data analyses).**
- **Briefing documents → outcome**: no systematic returns study found beyond the options paper above. **N.**
- **PDUFA extensions, late-cycle letters, adcomm cancellations, partner rights returns**: no study found. **N** (see the cases for why they are noisy).

### 1.7 Fraud / data-integrity tells
- Retractions/expressions of concern: data source exists (Crossref/Retraction Watch, F §11). No study links them to biotech returns. **N** (but see Cassava, Athira).
- Auditor changes, unusual sites, CRO changes: no biotech study found. **N.**
- Securities enforcement (SEC) and court complaints are *lagging* but give dated, sworn timelines that are excellent for the case library (see Applied Therapeutics).

**Bottom line Part 1:** for an outsider, the literature supports using *priors* (phase, area, genetic support, phase 2 quality, sponsor track record) and says little about *timing* signals. Every timing signal in our checklist is at best practitioner lore until we test it ourselves.

---

## Part 2. Forensic case studies

### Selection rule (stated before reading the cases)
1. Small/mid caps (roughly $0.3-10B before the event), 2018-2026, US-listed.
2. At least 6 blow-ups covering different mechanisms: phase 3 efficacy failure, efficacy-driven CRL, manufacturing CRL, integrity collapse, confirmatory-trial failure after approval.
3. At least 3 big winners (surprise readout, takeover).
4. At least 3 "false alarm" cases where loud warning signs preceded a good outcome.
5. Mix of areas (neuro, metabolic, oncology, rare disease, infectious disease, kidney, liver) and modalities (small molecule, antibody, cytokine, oncolytic virus, cell therapy, drug-Fc conjugate).
6. Drop a candidate if key dates could not be verified from at least one dated source.
Dropped after checking: Summit/ivonescimab (moves hard to date to a single event; became >$10B), bluebird bio (going-concern/reverse-split dates not verified), Sarepta Elevidys and Corcept (useful, used briefly in synthesis only), Frequency Therapeutics (used briefly).

Final set (14): **Blow-ups** Cassava, Athira, Applied Therapeutics, Scholar Rock, Tricida, Nektar, Replimune, Amylyx. **Winners** Karuna, Madrigal, Cidara. **False alarms** Axsome, Reata, Capricor. (Several cases contain both: Amylyx had a false-alarm phase before its blow-up; Capricor and Cidara are false alarms that turned into winners.)

Lead time = days from the signal becoming public to the main price event. Market caps are approximate.

---

### Case 1. Cassava Sciences (SAVA): simufilam, Alzheimer's — integrity concerns, then phase 3 failure
**Story.** Phase 2b data first failed (May 2020), then a "final" analysis in Sept 2020 was positive and the stock rose 133% that day ([Yahoo/TipRanks summary](https://news.yahoo.com/biotech-stock-moves-one-step-180348683.html); [Fierce](https://www.fiercebiotech.com/biotech/cassava-flunks-phase-3-alzheimers-test-triggering-early-end-second-trial-and-stock-crash)). On 25 Aug 2021 a citizen petition alleging data manipulation (filed by a law firm acting for short sellers) sent shares down ~31-32% (close $80.86, −$36.97) ([Fool](https://www.fool.com/investing/2021/08/27/why-cassava-sciences-is-plunging-again-today), [Docket Alarm complaint](https://www.docketalarm.com/cases/Texas_Western_District_Court/1--21-cv-00971/Rao_v._Cassava_Sciences_Inc._et_al/1)). **Main event:** 25 Nov 2024, RETHINK-ALZ missed all co-primary, secondary and biomarker endpoints; shares −85% ($26.48 → $3.91 at open) ([BioSpace](https://www.biospace.com/drug-development/cassavas-shares-plunge-as-alzheimers-drug-fails-phase-3)).

**Public signals before 25 Nov 2024**
| Date public | Signal | Source type (catalogue) | Lead time |
|---|---|---|---|
| May 2020 | Phase 2b initial analysis not significant | press release (D §1.3) | ~1,640 d |
| Sept 2020 | Positive re-analysis of the same trial | press release | ~1,530 d |
| 25 Aug 2021 | Citizen petition alleging Western-blot and biomarker manipulation | FDA docket (F §9), news | 1,188 d |
| Feb 2022 (approx.) | FDA denied the petition on procedural grounds (not on merits) | wiki-style source, **unverified** ([cavac](https://cavac.at/cavacopedia/Cassava%20Sciences)) | ~1,000 d |
| 27 Jun 2024 | Key academic collaborator (Hoau-Yan Wang) indicted for grant fraud related to early simufilam work ([STAT](https://www.statnews.com/2024/06/28/cassava-sciences-indictment-alzheimers-hoau-yan-wang/)) | news / DoJ | 151 d |
| 26 Sept 2024 | SEC settlement, $40M penalty; SEC alleged the 2020 phase 2b cognition results excluded ~40% of subjects; stock −11% after hours ([BioSpace](https://www.biospace.com/policy/cassava-agrees-to-pay-40m-fine-to-resolve-sec-probe-as-company-hit-with-new-lawsuit), [SEC](https://sec.gov/newsroom/press-releases/2024-151), [BNN Bloomberg](https://bnnbloomberg.ca/business/company-news/2024/09/26/cassava-to-pay-40-million-to-sec-over-alzheimers-drug-claims)) | SEC release, 8-K | 60 d |
| undated | PubPeer threads on founding papers | PubPeer (F §11) | undated |

**Missed?** No. The integrity debate was one of the most public in biotech, and the stock was a retail "meme" name. Yet on 22 Nov 2024 the market still valued it at roughly $1.2B (share count **unverified**), so a large residual probability of success was priced in. Short-interest data not found (**unverified**).
**Hindsight check.** "Failed trial rescued by re-analysis" + "SEC finding that results excluded subjects" is **high specificity** (rare in companies that later succeed). The petition alone is **medium**: petitions by short-side lawyers are rare and conflicted. Timing: useless for a 6-month window until the readout date was set.
**What an agent could have concluded.** "Pivotal programme rests on a phase 2b that first failed, then turned positive after re-analysis; regulator later said the reported analysis excluded 40% of subjects; avoid." It could *not* know the phase 3 result, but did not need to: an exclusion rule would have been enough.

### Case 2. Athira Pharma (ATHA): fosgonimeton, Alzheimer's — founder image manipulation, subgroup rescue, failure
**Story.** 17-18 June 2021: CEO/founder Leen Kawas placed on leave over altered images in her doctoral research (STAT); shares −39% ([GeekWire](https://www.geekwire.com/2021/athira-pharma-ceo-placed-leave-shares-plummet/), [MassDevice](https://www.massdevice.com/athira-pharmas-stock-falls-39-after-placing-its-ceo-on-leave/)); an internal probe later found altered images in her dissertation and ≥4 papers ([GeekWire](https://www.geekwire.com/2021/ex-athira-pharma-ceo-leen-kawas-resigns-leaves-board-image-manipulation-investigation/)). 22 June 2022: phase 2 ACT-AD missed its primary endpoint (and all secondaries); company highlighted a monotherapy subgroup; shares −67% to −78% ([Benzinga](https://www.benzinga.com/general/biotech/22/06/27809738/athira-pharma-shares-fall-to-52-week-low-read-here-why), [BioSpace "subgroup spin"](https://www.biospace.com/athira-puts-positive-spin-on-mid-stage-alzheimer-s-trial-flop)). **Main event:** 3-4 Sept 2024, phase 2/3 LIFT-AD (which had enriched for the subgroup) missed primary and key secondaries (GST p=0.70); shares −72% pre-market ([Clinical Trials Arena](https://www.clinicaltrialsarena.com/news/athiras-stock-topples-after-alzheimers-drug-flops-in-phase-ii-iii-trial/), [BioSpace release](https://www.biospace.com/drug-development/athira-pharma-announces-topline-results-from-phase-2-3-lift-ad-clinical-trial-of-fosgonimeton-for-mild-to-moderate-alzheimers-disease)).

| Date public | Signal | Source | Lead time to Sept 2024 |
|---|---|---|---|
| 17 Jun 2021 | Founder on leave; image-manipulation allegations on foundational papers | news, 8-K item 5.02 (not read), PubPeer | ~1,175 d |
| Oct 2021 | Founder resigns after probe confirms altered images | news | ~1,050 d |
| 22 Jun 2022 | Phase 2 missed primary; bull case moved to a post-hoc-looking subgroup | press release | 804 d |
**Missed?** No; each step caused a large drop. The residual question in 2022-2024 was whether the subgroup was real.
**Hindsight check.** Subgroup rescue after a clean miss: **high specificity** in this set (Athira, Cassava, Applied, Amylyx all ended badly; Reata is the counter-case, see Case 13). Founder integrity: **medium-high**, rare event.
**Agent.** Could flag "foundational science questioned + phase 3 enriched on a subgroup from a failed phase 2 → low prior". Could not know the result.

### Case 3. Applied Therapeutics (APLT): govorestat, classic galactosemia — efficacy CRL + warning letter
**Story.** Pivotal ACTION-Galactosemia Kids missed its primary endpoint (p=0.103) on 25 Apr 2023; company stressed trends and post-hoc analyses ([Medthority](https://www.medthority.com/news/2023/4/clinical-benefit-of-govorestat-in-action-galactosemia-kids-trial-company-plans-to-meet-with-fda-regarding-potential-nda-submission.-applied-therapeutics), [CheckRare](https://checkrare.com/clinical-trial-testing-govorestat/)). FDA cancelled the planned adcomm (18 Sept 2024): shares **+66-71%** ([Fool](https://www.fool.com/investing/2024/09/18/why-applied-therapeutics-stock-is-skyrocketing-tod), [Fierce](https://www.fiercebiotech.com/biotech/fda-scraps-adcomm-applieds-rare-disease-drug-ahead-november-decision)). **Main event:** CRL disclosed after close 27 Nov 2024; close $8.57 → $2.03 on 29 Nov (−76%); on 2 Dec a warning letter over the clinical study (electronic data deletion by a vendor, dosing errors) was disclosed ([BioSpace](https://www.biospace.com/fda/applied-therapeutics-crashes-after-fda-rejection-of-rare-disease-drug); class-action complaint, [Kaplan Fox PDF](https://kaplanfox.com/wp-content/uploads/2024/12/Applied-Therapeutics-Kaplan-Fox-FIling.pdf), allegations unproven).

Timeline below uses the complaint (a court document with dated, sourced quotes) for what was public; the BIMO inspection and Form 483 (Apr-May 2024) were **not public** at the time.
| Date public | Signal | Source | Lead time to 27 Nov 2024 |
|---|---|---|---|
| 25 Apr 2023 | Pivotal trial missed primary; post-hoc emphasis; concurrent $30M private placement at ~$0.95 ([Benzinga](https://benzinga.com/z/31959096)) | press release, 8-K | 582 d |
| 28 Feb 2024 | NDA accepted (PDUFA 28 Aug); equity raise the same day | press release, 424B5 (not read) | 273 d |
| 28 Mar 2024 | PDUFA extended 3 months (major amendment / "supplemental analyses") | 8-K, press release | 244 d |
| 7 Aug 2024 | Q2 release: a vendor had used an adult formula for ~1/3 of cognition scores; "corrected" data turned cognition **significant (p=0.032)**. RBC noted "data integrity and presentation had been a concern for some" | 10-Q/press release, analyst note quoted in complaint | 112 d |
| 12-14 Aug 2024 | CEO sold 777,014 shares (~$4.7M) | Form 4 (D §1.2) | ~105 d |
| 18 Sept 2024 | Adcomm cancelled (read by market as positive) | press release | 70 d |
**Missed?** Partly. The primary-endpoint miss and the "correction that improved the data" were public and noted by at least one analyst; the market nonetheless rallied ~70% on the adcomm cancellation. The inspection findings were private.
**Hindsight check.** "Data got *better* after an error correction" — **high specificity in spirit, but n=1 here** (Cassava's re-analysis is a cousin). Insider sale before PDUFA: **low** (common, often 10b5-1; plan status **unverified**). Adcomm cancellation: **low**, and it pointed the wrong way.
**Agent.** Could have concluded: "approval rests on a missed primary + post-hoc + vendor recalculation; FDA extended the review; base rate for such packages is poor; CEO selling." Could not have known about the 483 or the deleted data.

### Case 4. Scholar Rock (SRRK): apitegromab, SMA — manufacturing-only CRL
**Story.** Phase 3 SAPPHIRE was positive (Oct 2024, **from memory, unverified**). On 6 Aug 2025 (Q2 report) the company disclosed FDA observations at two CDMO sites, including Catalent Indiana (Novo-owned since Dec 2024), and said Novo had responded; stock fell 6.7-14% pre-market on a day that also had an earnings miss ([Investing.com transcript](https://ng.investing.com/news/transcripts/earnings-call-transcript-scholar-rocks-q2-2025-eps-miss-sends-stock-down-14-93CH-2046922), [Tiger](https://www.itiger.com/news/1103956749)). **Main event:** 23 Sept 2025 CRL "solely related to observations at Catalent Indiana"; shares −13%; "the stock has generally been weakening since news of the problems at the Catalent plant were first disclosed" ([Business Wire](https://www.businesswire.com/news/home/20250923756342/en), [pharmaphorum](https://pharmaphorum.com/news/manufacturing-issues-block-fda-nod-scholar-rock-sma-drug), [Pharma Letter](https://www.thepharmaletter.com/biotech-news/scholar-rock-shares-suffer-on-manufacturing-site-woes)). The same site caused a Regeneron CRL (July 2025) and Eylea delays ([Fierce Pharma](https://www.fiercepharma.com/manufacturing/regeneron-says-novo-plant-problems-caused-crl-and-will-delay-2-eylea-decisions)).
| Date public | Signal | Source | Lead time |
|---|---|---|---|
| ~late Jul / early Aug 2025 | Regeneron says Catalent Indiana problems held up its decisions (exact date **unverified**) | other company's release / trade press (F §1, F §5.1) | ~50-60 d |
| 6 Aug 2025 | Scholar Rock discloses CDMO observations | 10-Q / earnings call (D §1.5) | 48 d |
**Missed?** No, partly priced (two drops, ~−14% and −13%).
**Hindsight check.** A named fill-finish site with FDA observations shortly before PDUFA is **high specificity for a CMC-driven CRL or delay** (FDA rarely approves while the site is unresolved), but **low for permanent failure** (efficacy unaffected). Base rate: CMC/facility issues are the most common CRL reason (F §1).
**Agent.** Yes, realistically: map product → CDMO (10-K), watch other companies' disclosures about the same site, expect a delay; size accordingly. It could not know whether the reinspection would clear in time.

### Case 5. Tricida (TCDA): veverimer, metabolic acidosis in CKD — surrogate endpoint, single trial
**Story.** NDA for accelerated approval on one 12-week phase 3 (+40-week extension) using serum bicarbonate as a surrogate ([Fierce](https://www.fiercebiotech.com/biotech/tricida-sinks-as-fda-rejection-raises-prospect-new-trial)). 15-16 July 2020: FDA notice that "deficiencies preclude discussion of labeling"; shares −32% to −40% ([Fool](https://www.fool.com/investing/2020/07/16/heres-why-tricida-is-tanking-38-today.aspx), [Zacks](https://www.zacks.com/amp/stock/news/1008422/tricida-tcda-plummets-on-regulatory-update-on-veverimer)). 24 Aug 2020: CRL (FDA doubted the effect size would predict clinical benefit), −23% to −40% ([BioSpace](https://www.biospace.com/tricida-plunges-following-fda-rejection-of-metabolic-acidosis-in-ckd-treatment)). Appeal denied Feb 2021, ~−30% ([Fool](https://www.fool.com/investing/2021/02/26/heres-why-tricida-plummeted-today)). Oct 2022: outcome trial VALOR-CKD missed, ~−94%; Chapter 11 on 11 Jan 2023 ([Fierce](https://www.fiercebiotech.com/biotech/tricidas-shares-plunge-phase-3-fail-seals-fate-fda-rejected-kidney-drug), [BioSpace](https://www.biospace.com/tricida-s-stocks-crater-as-its-ckd-candidate-fails-in-phase-iii)).
| Date public | Signal | Source | Lead time to CRL |
|---|---|---|---|
| filing (2019, month **unverified**) | Accelerated approval sought on a single trial + novel surrogate | 10-K risk factors, press release | >1 y |
| 2020 (date **unverified**; BioWorld headline "In NDA review, FDA has concerns", page 403) | FDA concerns disclosed during review | 10-Q / press release | **unverified** |
| 15 Jul 2020 | "Deficiencies preclude labeling discussion" | 8-K / press release | 40 d |
**Missed?** No. The CRL was "foreshadowed" ([Endpoints headline](https://endpoints.news/?p=270802), [BioWorld "anticipated CRL"](https://www.bioworld.com/articles/496919-tricidas-veverimer-gets-its-anticipated-crl)). The final collapse came from a separate outcome trial two years later.
**Hindsight check.** Single trial + novel surrogate: **medium** (many rare-disease approvals rest on that). The late-cycle "deficiencies" letter: **high for "not approved on time", low for "never"** — compare Axsome (Case 12).
**Agent.** Could rate approval odds as low on design grounds and react to the July notice; the July notice itself is the price event, not a lead.

### Case 6. Nektar Therapeutics (NKTR): bempegaldesleukin (IL-2), melanoma — shrinking responses across data cuts
**Story.** June 2018 (ASCO): updated phase 1/2 PIVOT-02 data showed lower response rates (melanoma ORR 64% → 50%; response rate reported for a small share of dosed patients); shares −42% ([BioCentury](https://www.biocentury.com/article/295885/nektar-plummets-on-lower-than-expected-response-rates), [Fierce](https://www.fiercebiotech.com/biotech/asco18-mixed-reaction-to-nektar-s-confusing-nktr-214-trial), [search summary of Fool](https://www.fool.com/investing/2018/11/07/why-nektar-therapeutics-fell-365-in-october.aspx)). 1 Oct 2018: short seller Plainview, "Pegging the value of NKTR-214 at zero"; shares −7% ([BioCentury](https://www.biocentury.com/article/298334/nektar-falls-on-short-seller-report), [Fierce](https://www.fiercebiotech.com/biotech/nektar-s-long-acting-il-2-nktr-214-has-zero-value-claims-analyst)). **Main event:** 14 Mar 2022, phase 3 PIVOT IO-001 (783 pts) failed on PFS, ORR and (interim) OS vs nivolumab alone; shares −53% to −61% ($10.63 → $4.16) ([Fierce](https://www.fiercebiotech.com/biotech/bms-nektar-opdivo-combo-therapy-fails-phase-3-upset-once-largest-licensing-deal-biotech), [Fool](https://www.fool.com/investing/2022/03/14/why-nektar-therapeutics-stock-is-imploding-today)).
| Date public | Signal | Source | Lead time |
|---|---|---|---|
| Jun 2018 | Response rate fell across successive data cuts of a single-arm study; denominators changed | conference abstract/presentation (D §2.1) | ~1,370 d |
| Nov 2018 | Bladder cohort ORR 60% → 48% in updated abstract ([Fierce](https://www.fiercebiotech.com/biotech/bladder-cancer-readout-boosts-nektar-s-lead-i-o-drug), date per search summary) | conference abstract | ~1,220 d |
| 1 Oct 2018 | Short report arguing no added value over nivolumab | short report (E §5) | 1,260 d |
**Missed?** No: by March 2022 the stock had already lost most of its 2018 value (still fell ~60% on the day). Debate was open.
**Hindsight check.** "Effect shrinks as more patients are added to an open-label single-arm study" is **medium-high specificity** (regression to the mean is the default; Monzon 2015 shows single-arm phase 2 is a weak predictor in general). Short report: **low** on its own (see false alarms).
**Agent.** Could build a table of ORR by data cut and denominator from abstracts and flag decay; could not know the phase 3 result, and a 2018 signal says nothing about a 6-month window in 2022 other than "low prior".

### Case 7. Replimune (REPL): RP1 (vusolimogene, oncolytic virus) + nivolumab, melanoma — single-arm trial CRL
**Story.** BLA based on the single-arm phase 2 IGNYTE cohort (anti-PD-1-failed melanoma). **Main event:** 22 July 2025 CRL: IGNYTE "not adequate and well-controlled", results uninterpretable "due to heterogeneity of the patient population"; shares −76% from $12.09 ([AJMC](https://www.ajmc.com/view/fda-issues-crl-for-vusolimogene-oderparepvec-in-advanced-melanoma), [Investing.com](https://ng.investing.com/news/analyst-ratings/mizuho-analyst-comments-on-replimune-stock-decline-following-crl-93CH-2018933)). CEO: the issues "were not raised by the agency during the mid- and late-cycle reviews". Resubmitted Oct 2025; second CRL 10 Apr 2026 (−~20%); FDA said its advice against single-arm data had been "consistent since March 2021" ([BioSpace](https://www.biospace.com/fda/replimunes-advanced-melanoma-drug-rebuffed-by-fda-for-second-time)).
| Date public | Signal | Source | Lead time |
|---|---|---|---|
| filing / acceptance (dates **unverified**) | Approval sought on a single-arm study in a heterogeneous population, with a confirmatory trial still ongoing | press release, 10-K | months |
| May 2025 (from memory, **unverified**) | FDA leadership change at CBER with public scepticism of single-arm/surrogate approvals | news | ~2 months |
| — | FDA's March 2021 advice | **not public** until the 2026 CRL coverage | n/a |
**Missed?** Partly priced: Mizuho said the outcome "had been anticipated as a potential risk by some investors" (same link); the 76% drop shows the market put high odds on approval.
**Hindsight check.** Single-arm pivotal: **medium** (many oncology accelerated approvals used exactly this design; policy shift since 2025 changes the base rate). Company statements that FDA raised no concerns in mid/late-cycle: **zero informational value** (Replimune said it after the CRL; Corcept's published CRL later showed FDA had warned early, [BioSpace](https://www.biospace.com/fda/fda-warned-corcept-of-significant-review-issues-for-rejected-drug-in-early-meetings)).
**Agent.** Could note "regime risk": design accepted under old norms, judged under new ones. Could not see FDA's private advice. The FDA's now-published CRLs (F §4) are the tool to learn *after the fact* what FDA had said.

### Case 8. Amylyx (AMLX): Relyvrio (AMX0035), ALS — false alarm first, then the real failure
**Story.** Single 137-patient phase 2 (CENTAUR). 30 Mar 2022 adcomm voted 6-4 that data were insufficient, after FDA briefing documents signalled concerns ([Global Genes](https://globalgenes.org/?p=537300)). 7 Sept 2022 second adcomm voted 7-2 in favour ([Business Wire](https://www.businesswire.com/news/home/20220907006313/en/Amylyx-Pharmaceuticals-Announces-FDA-Advisory-Committee-Supports-Approval-of-AMX0035-for-the-Treatment-of-ALS)); approved 29 Sept 2022 under "regulatory flexibility" ([PharmTech](https://pharmtech.com/view/fda-approves-amylyx-pharmaceuticals-novel-als-treatment), [FDA Law Blog](https://www.thefdalawblog.com/2022/09/a-historic-day-in-drug-development-fda-approves-amylyxs-drug-to-treat-als-demonstrating-fdas-application-of-appropriate-flexibility-in-rare-diseases/)). **Main event:** 8 Mar 2024 confirmatory phase 3 PHOENIX missed primary and all secondaries; shares −82% close-to-close; drug withdrawn ([Zacks](https://www.zacks.com/amp/stock/news/2238847/amylyxs-amlx-als-drug-fails-pivotal-study-stock-down-82), [Fierce Pharma](https://www.fiercepharma.com/pharma/after-trial-failure-will-amylyx-pull-als-drug-relyvrio-market)).
| Date public | Signal | Source | Lead time to Mar 2024 |
|---|---|---|---|
| 2020-2021 | Single small phase 2; survival benefit only post hoc | publication, press releases | >2 y |
| 28-30 Mar 2022 | FDA briefing docs sceptical; negative adcomm vote | adcomm briefing doc (C §2) | 709 d |
**Missed?** No: the scepticism was FDA's own and public. But acting on it in 2022 (avoiding/shorting) would have been "wrong" for 18 months because approval came anyway.
**Hindsight check.** A small single trial with post-hoc survival: **medium-high specificity for eventual confirmatory failure**, **low specificity for the regulatory outcome** under rare-disease flexibility. The two outcomes must be separated in the case library.
**Agent.** Could hold two theses: "approval likely despite weak data (patient pressure, flexibility)" and "confirmatory trial likely to fail". It could not know the timing of PHOENIX within a 6-month window without the readout guidance.

### Case 9. Karuna Therapeutics (KRTX): KarXT (xanomeline-trospium), schizophrenia — surprise winner, then takeover
**Story.** IPO mid-2019; worth ~$400M ($17/share) on 15 Nov 2019 ([BioPharma Dive](https://www.biopharmadive.com/news/karuna-a-ha-moment-stock-swing-antipsychotic-drug/568094/)). **Event 1:** 18 Nov 2019 phase 2 EMERGENT-1 met primary (PANSS −11.6 vs placebo), discontinuations similar to placebo; shares +233% to +415% intraday, ~7x within two days ([Fool](https://www.fool.com/investing/2019/11/18/why-karuna-therapeutics-stock-is-skyrocketing-toda.aspx), [Pharma Letter](https://thepharmaletter.com/biotechnology/karuna-s-600-rise-reflects-schizophrenia-study-excitement)). **Event 2:** 22 Dec 2023 BMS agreed to buy at $330/share, ~53% premium, ~$14B ([Business Wire](https://www.businesswire.com/news/home/20231222091523/en/), [BioPharma Dive](https://www.biopharmadive.com/news/bristol-myers-karuna-acquire-schizophrenia-kar-xt/703313/)).
| Date public | Signal | Source | Lead time to Nov 2019 |
|---|---|---|---|
| Aug 2008 | Randomised, placebo-controlled pilot (n=20) of xanomeline in schizophrenia: better than placebo on BPRS/PANSS ([PubMed 18593778](https://pubmed.ncbi.nlm.nih.gov/18593778/)) | paper (PubMed/Europe PMC) | ~4,100 d |
| 1990s | Lilly's xanomeline: antipsychotic signal, dropped for GI/cholinergic side effects (BioPharma Dive, above) | historical literature | >20 y |
| 2019 | Karuna's thesis: add peripherally restricted trospium to block side effects (same source) | S-1 / IPO materials (not read) | months |
**Missed?** Yes, plausibly: a ~$400M valuation for a mechanism with prior randomised human efficacy and a mechanistic fix for the known failure mode. Scepticism was about psychiatry trial risk in general (same source).
**Hindsight check.** "Prior randomised human efficacy on the same endpoint, failure was due to tolerability, and the new product addresses tolerability" — **medium-high specificity** as a *positive* prior (rarely present in failures), but n is small and psychiatry placebo response is notoriously variable.
**Agent.** Could have found the 2008 paper via Europe PMC and articulated the variant perception. Could not know the effect size.

### Case 10. Madrigal Pharmaceuticals (MDGL): resmetirom, NASH/MASH — winner despite class failure and heavy shorting
**Story.** 31 May 2018 phase 2 biopsy data positive on NASH resolution (fibrosis modest: 29% vs 23%); shares +130% ([BioPharma Dive](https://www.biopharmadive.com/news/madrigal-scores-in-mid-stage-nash-study/524704/), [Fierce](https://www.fiercebiotech.com/biotech/madrigal-shares-jump-midstage-nash-results)). Class read-through: Intercept's obeticholic acid got a NASH CRL on 29 June 2020 (−~40%), after a PDUFA extension and two adcomm postponements ([Pharma Letter](https://thepharmaletter.com/article/in-another-blow-for-nash-as-intercept-gets-fda-rejection-for-obeticholic-acid), [Yahoo/Zacks on postponement](https://ca.news.yahoo.com/intercept-down-postponement-adcom-meet-171905599.html)). Jan 2022 safety phase 3 MAESTRO-NAFLD-1 positive (+13-18%) ([Fool](https://www.fool.com/investing/2022/01/31/why-madrigal-pharmaceuticals-stock-briefly-spiked)). **Main event:** 19 Dec 2022 phase 3 MAESTRO-NASH met both primary endpoints; shares +200-250% intraday (to ~$209 from ~$64); short interest reportedly >25% beforehand ([MarketBeat](https://www.marketbeat.com/originals/madrigal-pharmaceuticals-stock-is-up-200-in-one-day-heres-why), [TipRanks](https://www.tipranks.com/news/mdgl-skyrockets-after-positive-clinical-trial)).
| Date public | Signal | Source | Lead time |
|---|---|---|---|
| 31 May 2018 | Randomised phase 2 positive on biopsy endpoint aligned with the phase 3 endpoint | press release, AASLD abstract | 1,663 d |
| 29 Jun 2020 | Class/indication failure (Intercept CRL) — **negative** read-through | competitor 8-K (F §5.1) | 903 d |
| Dec 2022 | Short interest >25%, days-to-cover >7.5 — **negative** signal | FINRA short interest (E §5) | days |
**Missed?** The market gave it ~$1.2B (share count **unverified**) despite a positive randomised phase 2 on the same endpoint. Many investors were openly bearish (short interest). So: debated, priced as a long shot.
**Hindsight check.** Positive randomised phase 2 on the registrational endpoint: **medium** (Monzon 2015: positive phase 2 helps, but modestly). Negative class read-through and high short interest were **false alarms** here: mechanism (THR-β) differed from OCA (FXR).
**Agent.** Could have separated "indication risk" from "mechanism risk" and noted that the phase 3 endpoints matched the phase 2 biopsy endpoint. Could not know the result.

### Case 11. Cidara Therapeutics (CDTX): CD388 (drug-Fc conjugate), influenza prevention — partner handback, then winner and takeover
**Story.** CD388 licensed to J&J in 2021; J&J started handing it back in Sept 2023. 24 Apr 2024: Cidara reacquired rights (paying Janssen $85M upfront) with a $240M PIPE led by RA Capital with Bain Capital Life Sciences, BVF, Canaan ([BioSpace release](https://www.biospace.com/cidara-therapeutics-reacquires-global-development-and-commercial-rights-to-cd388-and-announces-private-placement-financing-of-240-million), [Cooley](https://www.cooley.com/news/coverage/2024/2024-04-24-cidara-therapeutics-announces-concurrent-reacquisition-of-ip-rights-to-cd388)). **Event 1:** 23 June 2025 phase 2b NAVIGATE met all primary and secondary endpoints; close $44.95, +113.8% ([BioWorld](https://www.bioworld.com/articles/721465-cidara-navigates-toward-new-flu-option-with-phase-iib-data)). **Event 2:** 14 Nov 2025 Merck agreed to buy at $221.50/share (~$9.2B), a 109% premium; shares had risen ~600% in the prior year ([Merck](https://www.merck.com/news/merck-to-acquire-cidara-therapeutics-inc-diversifying-its-portfolio-to-include-late-phase-antiviral-agent/embed/), [BioPharma Dive](https://www.biopharmadive.com/news/merck-cidara-acquire-flu-antiviral-drug/805513/)).
| Date public | Signal | Source | Lead time to Jun 2025 |
|---|---|---|---|
| Sept 2023 | Big-pharma partner exits the programme — **classically negative** | 8-K, partner pipeline (F §2.1) | ~640 d |
| 24 Apr 2024 | Specialist-fund-led $240M PIPE to buy the rights back | 8-K, Form D / 13D (D §1.2, §4) | 425 d |
**Missed?** Plausibly yes for the first leg (before NAVIGATE). The partner exit was part of J&J's broader retreat from infectious disease (widely reported; **not verified in this round**), i.e. strategic, not data-driven.
**Hindsight check.** Partner handback: **low specificity** on its own (strategic portfolio exits are common). Handback **plus** specialist-led financing at the same time: **medium**, plausible positive signal, no study found.
**Agent.** Could have asked "why did the partner leave (strategy vs data)?" and noted who funded the buy-back. Could not know NAVIGATE's result or Merck's interest.

### Case 12. Axsome Therapeutics (AXSM): AXS-05 (Auvelity), depression — false alarm (twice)
**Story.** FDA letter of 30 July 2021, disclosed 9 Aug 2021, said deficiencies precluded labeling discussions; shares −46.5% to $24.37 ([Fierce](https://www.fiercebiotech.com/biotech/fda-finds-fault-axsome-s-depression-filing-sinking-stock); figures per search summary of a [Fool piece](https://www.fool.com/investing/2021/09/23/why-wall-street-thinks-this-biotech-stock-can-trip)). April 2022: accepted FDA post-marketing requirements, +40% pre-market; approved ~19 Aug 2022 ([ChemDiv/Fierce repost](https://www.chemdiv.com/company/media/pharma-news/2022/axsome-agrees-to-post-marketing-commitments-with-fda-signaling-potential-ok-for-long-delayed-depress), [BioCentury](https://www.biocentury.com/article/644864/aug-19-quick-takes-at-long-last-fda-approves-axsome-s-antidepressant), [Zacks](https://www.zacks.com/amp/stock/news/1970946/axsome-axsm-soars-on-fda-nod-for-depression-drug-auvelity)). 11 June 2024: Culper short report alleging inflated Auvelity sales via consignment deals; shares −6-7% intraday; analysts dismissed it ([Fool](https://www.fool.com/investing/2024/06/11/why-axsome-therapeutics-stock-is-sinking-today), [TipRanks/Mizuho](https://www.tipranks.com/news/the-fly/mizuho-dismisses-axsome-short-report-after-management-call)).
**Signals:** the same late-cycle "deficiencies" letter as Tricida (Case 5), a delayed PDUFA, and an activist short report. **Outcome:** approval one year late; no collapse following the short report found as of this research (later share price **not verified**).
**Hindsight check.** This case is the control for Tricida: identical regulatory signal, opposite long-term outcome. The difference visible beforehand: Axsome had two positive randomised trials on a clinical endpoint (**from memory, unverified**: GEMINI phase 3 and ASCEND phase 2) vs Tricida's single surrogate-endpoint trial. Short report: **low** specificity.
**Agent.** Should treat the "deficiencies" letter as "approval delayed, check whether the deficiency is fixable (labeling/CMC/safety database) vs fundamental (efficacy evidence)".

### Case 13. Reata Pharmaceuticals (RETA): omaveloxolone (Skyclarys), Friedreich's ataxia — false alarm, then approval and takeover
**Story.** Single pivotal trial (MOXIe Part 2). 10 Aug 2020: FDA "not convinced the MOXIe results will support a single study approval", wants a second trial; shares −33% ([BioSpace](https://www.biospace.com/reata-shares-plummet-over-a-delay-in-seeking-regulatory-approval-for-friedreich-s-ataxia-treatment)). Nov 2020: FDA said a baseline-controlled analysis did not strengthen MOXIe; −7.6% ([search summary of BioCentury](https://www.biocentury.com/article/632284/friedreich-s-ataxia-program-hits-fda-snag-denting-reata-s-shares)). May 2021: FDA suggested a pre-NDA meeting (shares jumped) ([Fool](https://www.fool.com/investing/2021/05/19/why-reata-pharmaceuticals-is-skyrocketing-today)). 9 Aug 2022: mid-cycle concerns ("not exceptionally persuasive"), new analyses counted as a major amendment, PDUFA extended to 28 Feb 2023 ([Business Wire](https://www.businesswire.com/news/home/20220809005508/en/Reata-Pharmaceuticals-Announces-Three-Month-Extension-of-the-Review-Period-for-New-Drug-Application-for-Omaveloxolone-for-the-Treatment-of-Friedreich%E2%80%99s-Ataxia), [Benzinga](https://benzinga.com/z/28412974)). **Main events:** approved 28 Feb 2023 ([Drugs.com](https://Drugs.com/nda/omaveloxolone_220809.html)); 28 July 2023 Biogen agreed to buy at $172.50/share, ~59% premium, ~$7.3B EV ([BioSpace](https://www.biospace.com/biogen-boosts-neuro-pipeline-with-7-3b-reata-buy-on-the-heels-of-layoffs), [Investing.com](https://www.investing.com/news/stock-market-news/biogen-to-buy-reata-for-65-billion-to-bulk-up-rare-disease-portfolio-3137489)).
**Signals that were loud and wrong:** FDA asking for a second trial (in writing, per company), post-hoc supporting analyses rejected, PDUFA extension, mid-cycle scepticism, no adcomm.
**Hindsight check.** This is the key counter-example to "missed primary/post-hoc rescue = failure": here the primary *was met* in a randomised trial; the dispute was about whether one trial suffices. That distinction (met vs missed primary) separates Reata from Cassava, Athira and Applied.
**Agent.** Should have rated "single positive randomised trial in an ultra-rare disease with no therapy" as approvable under flexibility, despite FDA's early words. Could not know FDA's final stance.

### Case 14. Capricor Therapeutics (CAPR): deramiocel (cell therapy), DMD cardiomyopathy — CRL and short seller, then huge winner
**Story.** May 2025: FDA said it would hold an adcomm; late June 2025: cancelled "without explanation" ([Managed Healthcare Exec](https://www.managedhealthcareexecutive.com/view/capricor-s-dmd-cardiomyopathy-therapy-to-face-fda-advisory-committee), [Parent Project MD, 24 June 2025](https://www.parentprojectmd.org/capricor-shares-regulatory-update-on-deramiocel-bla-for-duchenne/)). 11 July 2025: CRL (insufficient evidence of effectiveness, plus CMC items); opened −38.6% at $6.99 ([BioSpace](https://www.biospace.com/fda/capricor-plunges-on-fda-rejection-of-dmd-cell-therapy), [Fierce](https://www.fiercebiotech.com/biotech/fda-rejects-capricors-dmd-cell-therapy-asks-more-data)). A well-known short seller publicly disclosed a short position (date **unverified**; [inkl headline](https://www.inkl.com/news/capricor-stock-soars-shkreli-is-short-here-s-what-pharma-bro-had-to-say)). **Main event:** 3 Dec 2025 phase 3 HOPE-3 positive (54% slower upper-limb decline per Fierce); prior close $6.36, ~+300% by mid-morning ([Fierce](https://www.fiercebiotech.com/biotech/capricor-sets-2nd-approval-attempt-duchenne-cell-therapy-phase-3-win), [RTTNews](https://www.rttnews.com/3600756/capricor-therapeutics-stock-skyrockets-over-340-on-positive-phase-3-hope-3-trial-results.aspx)). March 2026: FDA lifted the CRL, decision date 22 Aug 2026 ([BioSpace](https://www.biospace.com/fda/capricor-shares-rise-as-fda-lifts-duchenne-cell-therapy-rejection)); outcome of that decision **not found**.
**Signals before the winner:** adcomm cancellation (negative here, positive-looking for Applied), CRL on efficacy, CMC issues, short position. All negative; outcome strongly positive.
**What was knowable:** HOPE-3 was a randomised phase 3 with a known readout window (company guidance, **not verified**); the CRL concerned the *earlier* single-arm/HOPE-2 evidence. A CRL on old evidence says little about a new randomised trial.
**Hindsight check.** The case shows that "bad regulatory news" and "upcoming randomised readout" are separate bets. Specificity of CRL-as-negative for the *next* trial: **low**.

---

## Synthesis

### S1. Signal × outcome table (the hindsight problem made visible)
"Neg" = before a negative outcome; "Pos" = before a positive outcome; "FA" = false alarm (loud warning, good outcome). Lead time = range across the cases where it appeared.

| Signal | Neg cases | Pos cases | FA / wrong-way cases | Lead time | Open source (catalogue) | Specificity (judgement) |
|---|---|---|---|---|---|---|
| Primary endpoint missed; bull case rests on post-hoc, subgroup or "corrected" analysis | Cassava, Athira, Applied, Amylyx (survival post hoc) | — | none in set (Reata differs: primary met) | 1.5-4.5 y | press releases, 8-K, abstracts (D §1.3, §2.1) | **High** (n small; consistent with Boutron spin work and Monzon) |
| Data improved after an error correction / re-analysis | Cassava 2020, Applied Aug 2024 | — | — | 3.5 mo-4.5 y | press release, 10-Q | **High**, n=2 |
| Founder / key-paper integrity problem | Cassava, Athira | — | — | 1-3 y | PubPeer, Retraction Watch, news (F §11) | **Medium-high**, rare |
| Shrinking effect across open-label data cuts | Nektar (also Frequency's single-dose ph1/2 → failed ph2a, [Fool](https://www.fool.com/investing/2021/03/23/why-frequency-therapeutics-stock-is-crashing-today)) | — | — | 1-4 y | conference abstracts (D §2.1) | **Medium-high** |
| Named CDMO site with FDA observations before PDUFA | Scholar Rock (CRL), Regeneron (CRL) | — | — | ~7-8 weeks | other firms' releases, FDA 483/OAI, 10-Q (F §1) | **High for delay/CRL**, low for permanent failure |
| Single trial / surrogate / single-arm basis for approval | Tricida, Replimune, Amylyx (confirmatory), Capricor (CRL) | Reata (approved), Amylyx (approved first) | Reata | 1-3 y | 10-K, FDA guidance, published CRLs (F §4) | **Medium**; regime-dependent (2025+ FDA stricter) |
| FDA late-cycle "deficiencies preclude labeling" | Tricida | — | Axsome (approved 1 y later) | ~5-6 weeks | 8-K | High for "not on time", **low for "never"**; itself a price event |
| PDUFA extension (major amendment) | Applied, Intercept | Reata | Reata | 3-8 months | 8-K | **Low** |
| Adcomm cancelled / postponed | Applied (CRL), Capricor (CRL), Intercept (postponed → CRL) | — | Applied rose +70% on it | 1-2.5 months | press release, FDA calendar (C §2) | **Low, and misread by the market** |
| Negative adcomm / sceptical briefing docs | Amylyx (eventual) | — | Amylyx (approved anyway) | weeks-2 y | adcomm docs (C §2) | Medium (R-grade concordance data, but flexible in rare disease) |
| Activist short report / public short | Nektar (right, 3.5 y later), Cassava (petition, 3 y) | — | Axsome (no collapse found), Capricor (wrong) | days-years | short reports, news (E §9) | **Low** |
| High short interest before readout | — | Madrigal (>25%, then +200%) | Madrigal | days | FINRA (E §5) | **Low** (can mean squeeze) |
| Class/indication failure at a competitor | — | Madrigal (after Intercept CRL) | Madrigal | 2.5 y | competitor 8-K (F §5.1) | Low unless same mechanism |
| Partner hands back rights | — | Cidara | Cidara | ~1.7 y | 8-K, partner pipeline (F §2.1) | **Low** alone; check reason and who funds the buy-back |
| Specialist-led PIPE / financing | — | Cidara | — | ~14 months | 8-K, 13D/G (D §4) | Medium (vendor backtests only) |
| Insider open-market sale before PDUFA | Applied | — | — (not checked systematically) | ~3.5 months | Form 4 | **Low** (very common) |
| Prior randomised human efficacy on the same endpoint | — | Karuna (2008 paper), Madrigal (2018 ph2) | — | 1.5-11 y | PubMed/Europe PMC, abstracts | **Medium-high** as positive prior |
| Off-hours topline release | (AppliedXL: 27% vs 17% failures) | | | **0** (no lead) | newswire timestamp | Low and useless for forecasting |
| Late topline vs guidance | AppliedXL: no outcome difference | | | — | guidance vs release | **None** |

### S2. Ranked early indicators that look genuinely useful
Criteria: recurring in this set + plausibly specific + obtainable from open sources + early enough to matter. None is proven; each needs the proper study in S5.
1. **Missed primary + rescue analysis** (post-hoc, subgroup, recalculation, "trend"). Detect from press-release and abstract text. Strongest recurring tell; consistent with spin literature. Use: exclusion or strong negative prior.
2. **"Data improved after a correction/re-analysis"** — a sub-flag of 1; treat as a red flag requiring the original pre-specified analysis.
3. **Research-integrity problems on the founding science or founder** (PubPeer, retractions, university probes, SEC/DoJ actions). Rare but cheap to check once per programme.
4. **Manufacturing site status before a PDUFA date** (product → CDMO → inspection/483/OAI/warning letter, including other companies' disclosures about the same site). Weeks of lead time; specific for delay.
5. **Effect-size decay across data cuts** of open-label/single-arm studies (with denominator tracking).
6. **Evidence-package design vs current FDA practice**: single trial, single-arm, novel surrogate, heterogeneous population — scored against the published CRL library and recent decisions (regime-aware).
7. **Prior randomised human evidence on the registrational endpoint** (positive prior; Karuna, Madrigal).
8. **Met-vs-missed primary as a splitter for regulatory disputes**: if the primary was met (Reata, Axsome), FDA friction more often means delay than death; if missed (Applied, Tricida's surrogate doubt), death is likelier.
9. **Who finances, at what moment**: specialist-led PIPE around a strategic change (Cidara) vs company raising right after a miss at a deep discount (Applied Apr 2023).
10. **Base-rate priors** (phase/area/genetic support/biomarker/sponsor track record) from Part 1 — not timing signals, but they are the best-evidenced inputs.

**Look good in stories, fail the false-alarm test:** adcomm cancellation; PDUFA extension; late-cycle "deficiencies" letter as a terminal signal; short-seller reports; high short interest; competitor/class failure with a different mechanism; partner handback; insider sales; CMO departures (no evidence either way, F §11); late topline vs guidance; off-hours/Friday releases (no lead); pre-event price run-up (real on average, not usable without inside timing); company statements that "FDA raised no concerns".

### S3. Data streams this argues for (and against)
Build first:
1. **Press releases + 8-K text with a "result quality" extractor** (D §1.3, §1.2): primary met/missed, pre-specified vs post-hoc, subgroup emphasis, corrections. Highest value per effort in this set.
2. **Conference abstracts and data-cut history table per programme** (D §2.1): effect size and denominator by cut.
3. **Product → CDMO mapping + FDA inspection/warning-letter watch + other companies' disclosures about the same site** (F §1).
4. **Regulatory-communication extractor from 8-Ks** (PDUFA extension, late-cycle/labeling letters, adcomm scheduling) (C §2, D §1.2) — needed to *log* events and for the event study, not as stand-alone signals.
5. **Integrity check per programme**: Crossref/Retraction Watch + PubPeer for founding papers, plus enforcement news (F §11).
6. **Published FDA CRL library** (F §4) as the regime-aware prior for evidence packages.
7. **Europe PMC search for prior randomised human data on the mechanism** (positive prior).
8. **Form D/13D/8-K financing participants** (D §4) for "who is paying".
Deprioritise / argue against as *signals* (archive cheaply if at all): short-report monitoring and FINRA short interest as bearish inputs (keep only as risk/squeeze context, E §5); options-implied moves (no free history, E §4; keep only as "what is priced in"); release-timing features; adcomm cancellation as a positive; CT.gov completion-date slips (preprint: not predictive; but keep the daily snapshot for enrolment cuts and outcome changes, C §4, F §2.2).

### S4. Additions and corrections to the 14-point pre-readout checklist (F-overlooked §d)
- **#3 (power / post-hoc)**: sharpen to: "Did any earlier trial *miss* its pre-specified primary? Does the bull case rely on a subgroup, post-hoc, re-analysis or corrected dataset? Was the corrected data *better*?" → treat yes as a strong negative prior.
- **New #3b (data-cut drift)**: "List the effect size and denominator at each data cut. Is it shrinking?"
- **New #3c (prior human evidence)**: "Is there prior randomised human efficacy for this mechanism on this endpoint (incl. from earlier owners of the molecule)?"
- **#2 (endpoint accepted)**: add "single trial / single-arm / novel surrogate / heterogeneous population? Compare with published CRLs and decisions under the *current* FDA leadership." Do not trust company claims about FDA alignment.
- **New regulatory item**: "Log FDA process events (extension, late-cycle letter, adcomm scheduled/cancelled). Do NOT read adcomm cancellation as positive or an extension as negative. If FDA raised deficiencies, classify: fixable (labeling, CMC, safety database) vs fundamental (efficacy evidence); was the primary met?"
- **#11 (manufacturing)**: add "watch other sponsors' disclosures about the same site; a CRL elsewhere at the same site is the earliest warning".
- **#8 (insider/fund)**: downgrade Form 4 sales (common, often scheduled); upgrade "who led the last financing and at what moment (specialist-led PIPE vs distressed raise right after a miss)".
- **#9 (management)**: keep founder/scientist integrity issues; drop "CMO/CSO departure" as a scored signal until evidence exists (log only).
- **#13 (integrity)**: extend from retractions to PubPeer threads, university investigations, SEC/DoJ actions, and short-side citizen petitions (note conflicts; a petition is a reason to read the data, not a verdict).
- **New "two-thesis" rule**: for any approved-on-thin-data product, keep separate theses for "regulatory outcome" and "confirmatory trial outcome" (Amylyx).
- **New "market already knows" item**: "Has this signal already moved the price? Most tells in this set were priced within a day of becoming public; our edge, if any, is in combining them, not in seeing them first."
- **#14 (write it down)**: add "state which of the above signals are present *and* the base rate of failure for companies with the same signal pattern, from our own case library once built."

### S5. How the proper historical study should be designed (one page)
Goal: estimate, without hindsight or survivorship bias, how often each signal precedes bad/good outcomes and how much is already priced.
1. **Pre-register** (in the repo, dated, before looking at outcomes): signal definitions as executable rules (e.g. "press release contains 'did not meet' AND 'post hoc' or 'subgroup' within 30 days of topline"), outcome definitions (phase 3 met primary; FDA approval by PDUFA+90 d; abnormal return windows), and analysis plan. Commit hash = timestamp.
2. **Start from a complete population, not famous cases**: all industry-sponsored phase 2b/3 readouts and all PDUFA dates for US-listed companies with $0.3-10B cap in a fixed window (e.g. 2016-2024), from CT.gov (completed/terminated interventional trials with industry sponsors) joined to a ticker map, plus FDA approval/CRL lists (openFDA CRL library). Include delisted and bankrupt firms (survivorship).
3. **"What was known when"**: use CT.gov record versions (website history tab, manual/slow, or the project's own snapshots going forward), EDGAR *acceptance timestamps* (when a permitted access route exists; otherwise newswire timestamps), PubPeer/Crossref dates, FDA document posting dates, Wayback captures for pipeline pages. Every feature carries the timestamp of its first public appearance; features dated after the event are dropped.
4. **Matched controls**: for every event with signal X, compare with events without X, matched on phase, therapeutic area, modality, market cap bucket, year, and (for FDA events) review division. Report the false-alarm rate: P(signal | good outcome).
5. **Two separate questions**: (a) does the signal predict the *outcome*? (classification, calibration, base rate); (b) is it already in the *price*? (event study: abnormal returns from signal date to event date, against XBI, with the signal-day move excluded).
6. **Blind labelling**: whoever (or whichever LLM) codes the signal sees only documents up to the signal date, with company name and drug name masked where possible; outcomes coded by a separate pass. Measure inter-rater agreement on a sample.
7. **LLM leakage control**: if an LLM extracts features from historical text, test it on masked documents and check that its extractions do not differ when outcome-revealing context is present; never let it see post-event documents in the same prompt.
8. **Multiple testing**: limit to the ~10 pre-registered signals; correct for multiplicity; report confidence intervals; hold out the last 2 years as a test set.
9. **Report what fails**: publish null results in the case library so agents learn which tells are noise.
10. **Use results only as priors and checklist weights** for the forward-running agents, consistent with the project rule that historical cases never score the agents.

### S6. Limits of this first pass
- 14 hand-picked cases, chosen after the outcomes were known: **this proves nothing statistically**; at best it generates hypotheses for S5.
- All filing content came from secondary sources (news, press-release mirrors, a court complaint); **no EDGAR filing and no CT.gov history was read**. Several dates are marked unverified.
- Price moves are as reported, often intraday/pre-market; sources differ by several points.
- Several academic results were taken from abstracts or search summaries, not full texts (Lo 2019 AUCs, BIO 2021 figures, Wong 2019 POS, the 2000 J Investig Med study's authors, short-report studies). The Feuerstein-Ratain JNCI source was not found.
- Survivorship within cases: I could only describe signals someone wrote about. Signals that were present but never reported (e.g. silent CT.gov edits) are invisible here, which biases the set towards "loud" signals.
- Regime change: FDA practice in 2025-2026 (fewer adcomms, published CRLs, stricter stance on single-arm data in some divisions) means pre-2025 base rates for regulatory signals may not transfer.
- The AppliedXL findings are from a vendor report (July 2026), not peer-reviewed.
