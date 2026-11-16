# Case forensics: were there early indicators that people missed?

Research night of 2026-11-15, added at the owner's request ("backtrace like forensics"). A first pass, not the historical study
planned in the README. Full case timelines with every dated signal: [notes/G-forensics.md](notes/G-forensics.md).

**Read this first**
- **Fourteen hand-picked cases prove nothing statistically.** Every case was chosen after its outcome was known. They produce
  hypotheses for the proper study (section 7), not evidence that a signal works.
- **These cases are for people, not for the agents.** The models know how they ended. They must never be shown to an agent as
  if open, and never used to score the agents (project rule).
- Facts come from the linked press, trade press and one court filing. **No SEC filing and no trial-registry history was read**
  (SEC requires a contact e-mail in every request). Dates and price moves are as reported; sources differ by a few points.
  I checked the main events against what I know and found no conflicts; I did not re-verify each date at its source.
- Not investment advice.

## 1. The answer in short

1. **Most "missed" signals were not missed.** They were public, argued over, and moved the price on the day they appeared.
   Where the market went wrong, if anywhere, it was at the *second* step: believing the rescue. (Pricing a long shot that
   then fails is not by itself a mistake.) Cassava's positive "re-analysis" of a failed
   trial; Applied Therapeutics' corrected data that happened to turn significant; a 70% rally when FDA cancelled Applied's
   advisory meeting, two months before the rejection.
2. **A few patterns came before bad outcomes and were absent before good ones:**
   - an earlier trial that missed its main goal, with the optimistic case resting on subgroups, after-the-fact analyses or
     corrected data;
   - integrity problems with the founder or the founding science;
   - a named manufacturing site with FDA findings shortly before a decision date;
   - a treatment effect that shrinks each time more patients are reported.
3. **Several famous "tells" did not separate bad from good outcomes in this set.** An extended review, the late
   "deficiencies" notice, high short interest and a competitor's failure each also came before a good outcome. A cancelled
   advisory meeting came before two rejections, but the market read it as good news. A partner handing back rights came
   before a success. Short-seller reports were right twice, years early, and wrong at least once.
4. **Published research supports background odds, not timing signals.** Phase and disease base rates, genetic support, a
   positive earlier trial and the sponsor's track record have real evidence. Almost every timing signal is practitioner lore.
5. **A candidate question to split a regulatory dispute:** did the pivotal trial meet its pre-set main goal? If yes
   (Reata; Axsome too, though its trial history was written from memory and is unverified), friction with FDA mostly meant delay. If no, or if the goal itself was doubted (Applied, Tricida), it
   mostly meant failure.

## 2. What published research says

Strength: **R** replicated, **S** single peer-reviewed study, **P** practitioner or vendor analysis, **L** lore, **N** nothing found.

| Signal | Finding | Strength | Use for us |
|---|---|---|---|
| Price or options activity before results | Shares rose more before positive than negative cancer-trial results ([Rothenstein et al., JNCI 2011](https://www.sciencedaily.com/releases/2011/09/110926165902.htm), 59 trials; wide uncertainty). Unusual options trading before FDA advisory meetings, strongest for small firms ([Wu, Borochin, Golec 2024](https://ideas.repec.org/a/eee/corfin/v84y2024ics092911992300144x.html); [Bohmann, Patel 2022](https://ideas.repec.org/a/bla/jbfnac/v49y2022i7-8p1211-1236.html)) | R that leakage exists | Low: insiders know things; an outsider cannot time it, and free options history does not exist |
| Base rates by phase and disease | [Wong, Siah, Lo 2019](https://dspace.mit.edu/handle/1721.1/128480); [Hay et al. 2014](https://pubmed.ncbi.nlm.nih.gov/24406927/); [BIO 2011-2020](https://www.bio.org/clinical-development-success-rates-and-contributing-factors-2011-2020) | R | High, as the starting estimate |
| Genetic support for the target | About 2 to 2.6 times higher success (Nelson 2015, Minikel 2024; see [DATA-SOURCES.md](DATA-SOURCES.md) 9.6) | R | High, as background |
| Positive phase 2 | Associated with a positive phase 3 in cancer; a randomised phase 2 predicted no better than a single-arm one ([Monzon et al. 2015](https://experts.mcmaster.ca/display/publication1536798)) | S | Medium |
| No phase 2 at all | 42% of failed cancer phase 3 trials had none ([Addeo et al., JAMA Netw Open 2019](https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2733181)) | S, no controls | Medium |
| Sponsor track record, enrolment speed | Among top predictors in a machine-learning study ([Lo, Siah, Wong 2019](https://cancerx.mit.edu/machine-learning-with-statistical-imputation-for-predicting-drug-approvals), figures via summary) | S | Medium |
| "Small company, cancer phase 3, always fails" (Feuerstein-Ratain rule) | Authors' own tally; the journal source could not be found; no independent replication | L / P | Read as "the market already prices low odds" |
| Spin in trial reports | Common: in 58% of abstract conclusions of trials with a non-significant main result ([Boutron et al., JAMA 2010](https://www.globalfamilydoctor.com/Resources/A-Ztopiclisting/JournalWatch/Howmuchspinistherewithnonsignificantresults63.aspx)) | R that spin is common; N that it predicts returns | Supports checking result quality |
| "Good news travels fast" (late results are bad) | **Not supported**: late readouts met their goal 53% of the time against 55-56% for on-time or early ([AppliedXL 2026](https://appliedxl.com/research/readout-gap), vendor, 681 trials) | P, against | Drop as a signal |
| Results released outside market hours | Fail more often, 27% against 17% (same report) | P | None: no lead time |
| FDA follows its advisory committee | About 80-90% of the time ([JAMA Health Forum](https://jamanetwork.com/journals/jama-health-forum/fullarticle/2807050)) | R | Fewer events now that meetings are rare |
| Short-seller reports, short interest predicting failure | General-market studies only; nothing biotech-specific | N | See false alarms below |
| Retractions, auditor changes, executive departures | No study linking them to biotech returns | N | Log, do not score |

## 3. The cases

Selection rule, fixed before reading them: small and mid-size US-listed companies, 2018-2026; at least six failures of
different kinds, three winners, and three **false alarms** where loud warnings were followed by a good outcome; mixed disease
areas and drug types; dropped if key dates could not be sourced. Dropped after checking: Summit (moves hard to tie to one
event, and too large), bluebird bio (dates not verified), Sarepta, Corcept and Frequency Therapeutics (used only in passing).

### Failures

| Company, drug | Price event | What was public beforehand | Lead time | Was it missed? |
|---|---|---|---|---|
| **Cassava**, simufilam (Alzheimer's) | 25 Nov 2024: phase 3 failed, shares -85% ([BioSpace](https://www.biospace.com/drug-development/cassavas-shares-plunge-as-alzheimers-drug-fails-phase-3)) | 2020: phase 2 first failed, then a positive re-analysis. Aug 2021: petition alleging manipulated data, -31% ([Fool](https://www.fool.com/investing/2021/08/27/why-cassava-sciences-is-plunging-again-today)). June 2024: a key academic collaborator was indicted, which is an accusation and not a conviction; the later outcome was not checked ([STAT](https://www.statnews.com/2024/06/28/cassava-sciences-indictment-alzheimers-hoau-yan-wang/)). Sept 2024: settlement with the regulator (SEC), which alleged that the reported result left out about 40% of patients ([BioSpace](https://www.biospace.com/policy/cassava-agrees-to-pay-40m-fine-to-resolve-sec-probe-as-company-hit-with-new-lawsuit)) | 2 months to 4.5 years | No. One of the most public disputes in biotech; still valued around $1 billion days before (share count unverified) |
| **Athira**, fosgonimeton (Alzheimer's) | Sept 2024: phase 2/3 failed, -72% ([Clinical Trials Arena](https://www.clinicaltrialsarena.com/news/athiras-stock-topples-after-alzheimers-drug-flops-in-phase-ii-iii-trial/)) | June 2021: founder on leave over altered images in her research, -39% ([GeekWire](https://www.geekwire.com/2021/athira-pharma-ceo-placed-leave-shares-plummet/)). June 2022: phase 2 missed; company pointed to a subgroup ([BioSpace](https://www.biospace.com/athira-puts-positive-spin-on-mid-stage-alzheimer-s-trial-flop)) | 2 to 3 years | No; each step caused a large fall |
| **Applied Therapeutics**, govorestat (rare metabolic disease) | 27 Nov 2024: FDA rejection, -76%; warning letter days later ([BioSpace](https://www.biospace.com/fda/applied-therapeutics-crashes-after-fda-rejection-of-rare-disease-drug)) | Apr 2023: pivotal trial missed its main goal. Mar 2024: review extended. Aug 2024: a recalculation made the result significant; according to the complaint cited below, the chief executive sold shares days later (whether under a pre-set selling plan is unverified). Sept 2024: advisory meeting cancelled, **shares +70%** ([Fierce](https://www.fiercebiotech.com/biotech/fda-scraps-adcomm-applieds-rare-disease-drug-ahead-november-decision)). Timeline from a [court complaint](https://kaplanfox.com/wp-content/uploads/2024/12/Applied-Therapeutics-Kaplan-Fox-FIling.pdf) (allegations unproven) | 2 to 19 months | **Partly.** The public facts pointed down while the market rallied. The inspection findings were private |
| **Scholar Rock**, apitegromab (spinal muscular atrophy) | 23 Sept 2025: rejection for manufacturing only, -13% ([pharmaphorum](https://pharmaphorum.com/news/manufacturing-issues-block-fda-nod-scholar-rock-sma-drug)) | Summer 2025: Regeneron blamed the same plant for its own rejection. 6 Aug 2025: Scholar Rock disclosed FDA findings at its manufacturers | About 7 weeks | No; partly priced in two steps |
| **Tricida**, veverimer (kidney disease) | July-Aug 2020: FDA flags deficiencies, then rejects, -30 to -40% each ([Fierce](https://www.fiercebiotech.com/biotech/tricida-sinks-as-fda-rejection-raises-prospect-new-trial)); Oct 2022: outcome trial failed, -94% ([Fierce](https://www.fiercebiotech.com/biotech/tricidas-shares-plunge-phase-3-fail-seals-fate-fda-rejected-kidney-drug)) | Approval sought on one short trial with a new stand-in measure for benefit | Over a year | No; the rejection was widely expected |
| **Nektar**, bempegaldesleukin (melanoma) | 14 Mar 2022: phase 3 failed, about -60% ([Fierce](https://www.fiercebiotech.com/biotech/bms-nektar-opdivo-combo-therapy-fails-phase-3-upset-once-largest-licensing-deal-biotech)) | June 2018: response rate fell from 64% to 50% as more patients were reported, -42% ([BioCentury](https://www.biocentury.com/article/295885/nektar-plummets-on-lower-than-expected-response-rates)). Oct 2018: short-seller report | 3.5 years | No; the shares had lost most of their value before |
| **Replimune**, RP1 (melanoma) | 22 July 2025: rejection, -76% ([AJMC](https://www.ajmc.com/view/fda-issues-crl-for-vusolimogene-oderparepvec-in-advanced-melanoma)); second rejection Apr 2026 ([BioSpace](https://www.biospace.com/fda/replimunes-advanced-melanoma-drug-rebuffed-by-fda-for-second-time)) | Approval sought on a trial without a control group, in a mixed patient group. FDA's earlier advice against this was not public | Months | **Partly.** The fall shows approval was widely expected |
| **Amylyx**, Relyvrio (ALS) | 8 Mar 2024: confirmatory trial failed, -82% ([Fierce Pharma](https://www.fiercepharma.com/pharma/after-trial-failure-will-amylyx-pull-als-drug-relyvrio-market)) | One small trial; survival benefit found only afterwards. Mar 2022: FDA's own reviewers sceptical; advisory vote 6-4 against. Approved anyway in Sept 2022 | 2 years | No. But acting on the scepticism in 2022 was "wrong" for 18 months |

### Winners

| Company, drug | Price event | What was public beforehand | Was it missed? |
|---|---|---|---|
| **Karuna**, KarXT (schizophrenia) | 18 Nov 2019: phase 2 success, shares up several-fold ([BioPharma Dive](https://www.biopharmadive.com/news/karuna-a-ha-moment-stock-swing-antipsychotic-drug/568094/)); Dec 2023: bought by BMS for about $14 billion ([BioPharma Dive](https://www.biopharmadive.com/news/bristol-myers-karuna-acquire-schizophrenia-kar-xt/703313/)) | A 2008 controlled pilot trial had shown the active ingredient worked in schizophrenia ([PubMed](https://pubmed.ncbi.nlm.nih.gov/18593778/)); it had been shelved for side effects, which Karuna's second ingredient was designed to block | Perhaps: about $400 million for a mechanism with prior human evidence and a specific fix. But the pilot had 20 patients, and placebo response in psychiatry trials varies a lot |
| **Madrigal**, resmetirom (fatty liver disease) | 19 Dec 2022: phase 3 success, +200% or more ([MarketBeat](https://www.marketbeat.com/originals/madrigal-pharmaceuticals-stock-is-up-200-in-one-day-heres-why)) | May 2018: positive controlled phase 2 on the same measure as the phase 3 ([BioPharma Dive](https://www.biopharmadive.com/news/madrigal-scores-in-mid-stage-nash-study/524704/)). Against it: a competitor's rejection in the same disease (2020) and over 25% of shares sold short | Debated and priced as a long shot |
| **Cidara**, CD388 (flu prevention) | 23 June 2025: phase 2b success, +114% ([BioWorld](https://www.bioworld.com/articles/721465-cidara-navigates-toward-new-flu-option-with-phase-iib-data)); Nov 2025: bought by Merck for about $9.2 billion ([BioPharma Dive](https://www.biopharmadive.com/news/merck-cidara-acquire-flu-antiviral-drug/805513/)) | Sept 2023: partner J&J handed the drug back. Apr 2024: specialist funds led a $240 million financing to buy the rights ([BioSpace](https://www.biospace.com/cidara-therapeutics-reacquires-global-development-and-commercial-rights-to-cd388-and-announces-private-placement-financing-of-240-million)) | Perhaps, for the first leg |

### False alarms

| Company, drug | The loud warnings | What happened |
|---|---|---|
| **Axsome**, Auvelity (depression) | Aug 2021: the same "deficiencies" notice from FDA that Tricida got, -46% ([Fierce](https://www.fiercebiotech.com/biotech/fda-finds-fault-axsome-s-depression-filing-sinking-stock)) | Approved a year late, Aug 2022 ([BioCentury](https://www.biocentury.com/article/644864/aug-19-quick-takes-at-long-last-fda-approves-axsome-s-antidepressant)). A short-seller report followed in June 2024, after approval; what happened to the shares later was not checked |
| **Reata**, Skyclarys (Friedreich's ataxia) | Aug 2020: FDA said one trial would not be enough, -33% ([BioSpace](https://www.biospace.com/reata-shares-plummet-over-a-delay-in-seeking-regulatory-approval-for-friedreich-s-ataxia-treatment)). Supporting analyses rejected; review extended; no advisory meeting | Approved Feb 2023; bought by Biogen for about $7.3 billion in July 2023 ([BioSpace](https://www.biospace.com/biogen-boosts-neuro-pipeline-with-7-3b-reata-buy-on-the-heels-of-layoffs)) |
| **Capricor**, deramiocel (Duchenne heart disease) | June 2025: advisory meeting cancelled. July 2025: rejection, -39% ([BioSpace](https://www.biospace.com/fda/capricor-plunges-on-fda-rejection-of-dmd-cell-therapy)). A well-known short seller declared a position (date unverified) | 3 Dec 2025: phase 3 success, about +300% ([Fierce](https://www.fiercebiotech.com/biotech/capricor-sets-2nd-approval-attempt-duchenne-cell-therapy-phase-3-win)). FDA's later decision not found |

**Two pairs worth remembering**
- *Tricida and Axsome* got the identical FDA notice. Tricida had one trial on a stand-in measure; Axsome had controlled trials
  on a clinical measure (from the research agent's memory, unverified). One collapsed, one was approved.
- *Applied and Capricor* both had an advisory meeting cancelled before a rejection. For Applied the market cheered it. For
  Capricor the rejection concerned old evidence, and a new controlled trial then succeeded. Bad regulatory news and an
  upcoming trial result are separate bets.

## 4. Signals against outcomes

This table makes the hindsight problem visible: a signal only counts if it is rare before good outcomes. **Caution:** the
positive signals at the bottom were looked for in the winners only, not in the failures, so their ratings are the weakest here.

| Signal | Before failures | Before successes or false alarms | Lead time | Specificity (judgement) |
|---|---|---|---|---|
| Earlier trial missed its main goal; hopes rest on subgroup, after-the-fact or corrected analysis | Cassava, Athira, Applied, Amylyx | None in this set | 1.5 to 4.5 years | **High**, small sample |
| Data got *better* after a correction or re-analysis | Cassava, Applied | None | 3.5 months to 4.5 years | **High**, two cases |
| Integrity problem with founder or founding papers | Cassava, Athira | None | 1 to 3 years | Medium-high, rare |
| Effect shrinks as more patients are reported | Nektar | None | 1 to 4 years | Medium-high |
| Named manufacturing site with FDA findings before a decision | Scholar Rock, Regeneron | None | About 7 weeks | **High for delay**, low for permanent failure |
| Approval sought on one trial, no control group, or a stand-in measure | Tricida, Replimune, Amylyx, Capricor | Reata approved; Amylyx approved at first | 1 to 3 years | Medium; depends on FDA's current stance |
| FDA "deficiencies" notice late in review | Tricida | Axsome approved a year later | 5 to 6 weeks | High for "not on time", **low for "never"** |
| Review extended | Applied | Reata | 3 to 8 months | **Low** |
| Advisory meeting cancelled | Applied, Capricor | No good outcome in this set; but the market read it as good news | 1 to 2.5 months | Unclear from two cases; **misread by the market** |
| Short-seller report or public short | Nektar, Cassava (years later) | Capricor (date unverified). Axsome's came after approval and is not counted | Days to years | **Low** |
| High short interest before a readout | - | Madrigal, then +200% | Days | **Low** |
| Competitor fails in the same disease | - | Madrigal | 2.5 years | Low unless same mechanism |
| Partner hands back rights | - | Cidara | 1.7 years | **Low** alone |
| Insider sale before a decision | Applied | **Not checked** in the other cases | 3.5 months | Unknown here; such sales are very common |
| Specialist funds lead a financing | - | Cidara | 14 months | Medium; no study |
| Earlier controlled human evidence on the same measure | **Not checked** in the failures | Karuna, Madrigal | 1.5 to 11 years | Promising, untested |

## 5. What looks useful, and what does not

**Looks useful** (recurring here, plausibly specific, obtainable from open sources, early enough). None is proven.
1. A missed main goal followed by a rescue analysis. Strongest recurring pattern.
2. Data that improved after a correction: ask for the original pre-planned analysis.
3. Integrity problems around the founding science. Rare, cheap to check once per programme.
4. The manufacturing site's status before a decision date, including what *other* companies say about the same site.
5. Effect size by data release, with the number of patients each time.
6. The evidence package against FDA's current practice, using the published rejection letters.
7. Earlier controlled human evidence on the same measure, including from previous owners of the molecule.
8. Met or missed main goal, as the splitter in a regulatory dispute.
9. Who finances, and when: specialist-led financing around a strategic change, against a distressed raise right after a miss.
10. Background odds: phase, disease, genetics, sponsor record.

**Good stories that did not hold up here:**
- *Also seen before good outcomes:* extended review; the late "deficiencies" notice as a final verdict; high short interest;
  competitor failure with a different mechanism; partner handback; short-seller reports.
- *Misread by the market:* a cancelled advisory meeting.
- *No support in the research:* late results; release timing (no lead time); price run-ups (real on average, unusable).
- *Not checked or no evidence either way:* insider sales; executive departures.
- *Worthless:* company statements that "FDA raised no concerns" (said by Replimune after its rejection; a published letter later showed FDA had warned another company
early, [BioSpace](https://www.biospace.com/fda/fda-warned-corcept-of-significant-review-issues-for-rejected-drug-in-early-meetings)).

**The uncomfortable part.** Most of these signals were priced within a day of becoming public. If there is an edge, it is in
combining them and in not believing the rescue, not in seeing them first. And the useful ones have long lead times: they tell
a long-only fund what to *avoid*, not when something will happen.

## 6. What this changes in the other reports

**Data streams it argues for** (additions to [DATA-SOURCES.md](DATA-SOURCES.md) section 13):
- A "result quality" reading of every results press release: main goal met or missed, pre-planned or after-the-fact, subgroup
  emphasis, corrections. Highest value for effort in this set; it sits on streams 1 and 6 of the top 10.
- A table of effect size and patient numbers per data release, from conference abstracts and press releases.
- Manufacturer mapping and inspection watch, including other companies' disclosures about the same site.
- A one-off integrity check per programme.
- The published rejection letters as the reference for what FDA currently accepts.
- A literature search for earlier controlled human data on the mechanism.

**Streams it argues against as signals** (keep only as context): short-seller reports and short interest as bearish inputs;
options data; release timing; completion-date slips in the registry (keep the daily copies for endpoint and enrolment changes).

**Changes to the pre-readout checklist** ([DATA-SOURCES.md](DATA-SOURCES.md) 9.9):
- Item 3 becomes: has any earlier trial missed its pre-set main goal? Does the case rely on a subgroup, re-analysis or
  corrected data? Did the correction make the data better?
- New: list effect size and patient numbers at each data release. Is it shrinking?
- New: is there earlier controlled human evidence for this mechanism on this measure?
- Item 2 adds: one trial, no control group, a stand-in measure, a mixed patient group? Compare with published rejection
  letters under current FDA leadership. Do not rely on company claims of agreement with FDA.
- New: log FDA process events without scoring them. If FDA raised deficiencies, classify them as fixable (labelling,
  manufacturing, safety data) or fundamental (evidence of benefit).
- Item 11 adds: watch other companies' disclosures about the same manufacturing site.
- Item 8: downgrade insider sales; upgrade who led the last financing and at what moment.
- Item 9: keep founder and integrity issues; log executive departures without scoring them.
- Item 13: extend from retractions to critiques on PubPeer, university investigations, regulator or court actions, and
  petitions from short sellers (a reason to read the data, not a verdict; note the conflict of interest).
- Item 14 adds: state which signals are present and, once our own case library exists, how often that pattern failed.
- New: keep separate theses for "will it be approved" and "will the confirmatory trial succeed" (Amylyx).
- New: has this signal already moved the price?

**No case names in the agents' template.** The checklist goes to the agents as questions only. Company names and examples
from this report stay out of it, because the models know how those cases ended.

## 7. How the proper historical study should be set up

The README plans event studies and a case library. To avoid the hindsight built into this first pass:
1. **Write the rules down first.** Signal definitions, outcome definitions and the analysis plan go into the repository,
   dated, before any outcome is looked at.
2. **Start from a complete list, not famous cases.** All phase 2b and phase 3 readouts and all FDA decision dates for
   US-listed companies in the size range over a fixed period, including companies that were delisted or went bankrupt.
3. **Date every fact by when it became public.** Registry versions, filing timestamps, publication dates, archived web
   pages. Anything dated after the event is dropped.
4. **Compare with matched companies** where the signal was absent: same phase, disease area, drug type, size and year.
   Report how often the signal appeared before *good* outcomes.
5. **Ask two separate questions.** Does the signal predict the outcome? And was it already in the price?
6. **Label blind.** Whoever codes a signal, person or model, sees only documents up to that date, with names masked where
   possible.
7. **Check for model memory.** If a model extracts features from old documents, test that its output does not change when
   outcome-revealing context is present.
8. **Limit the number of signals tested** to about ten fixed in advance, and hold back the most recent two years as a check.
9. **Publish what fails.**
10. **Use the results only as starting odds and checklist weights**, never to score the agents.

This study needs SEC access (a contact e-mail) and the registry's version history, which the open API does not provide. Both
are owner decisions listed in [DATA-SOURCES.md](DATA-SOURCES.md) section 15 (points 1 and 11).

## 8. Limits
- Hand-picked cases, chosen with hindsight.
- Secondary sources only; several dates are marked unverified in the notes (Tricida's filing date, Replimune's acceptance
  date, the date Regeneron disclosed the plant problem, the Capricor short position). Scholar Rock's and Axsome's trial
  histories were written from memory by the research agent.
- Only signals that someone wrote about are visible. Quiet ones, such as silent registry edits, cannot be found this way,
  which tilts the set towards loud signals.
- FDA practice changed in 2025-2026 (fewer advisory meetings, published rejection letters, a stricter line on trials without
  a control group in some divisions), so older regulatory patterns may not carry over.
- Several research figures come from abstracts or summaries, not full papers. The AppliedXL report is a vendor publication.
