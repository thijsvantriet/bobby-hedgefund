# 0005. Paper funds: where the books are kept, how orders are booked, costs, splits and takeovers
Date: 2026-11-17
Status: proposed

## Context
Five paper funds and 1,000 random "Dice" funds each start with $1,000,000 of paper money and trade once a day at
most (`docs/SPEC.md`, section 4). **There is no broker and there are no real orders**: a "trade" is a line in our
own books. Those books decide every figure the experiment reports, so their rules are fixed before the pilot.

The spec chose: orders as a percentage of the fund turned into whole shares at the fill price; sells before buys;
buys cut down in proportion when cash is short; the fill at the next opening price; an order waits at most 5
trading days for an opening price; no trade under 0.5% of the fund; long only, no borrowing, cash earns nothing;
starting trading costs of 0.25%, 0.5% and 1.0% by company size, to be checked in the pilot; share splits, takeovers
and delistings booked by script from SEC filings. Left to this record: where the books live, the exact booking
rules, how the costs are checked, and one rule per kind of company event.

Existing trading programs were considered in the research and rejected: they are built for other jobs, and the
hard part (the company events) must be supplied by us anyway (`docs/research/OPEN-SOURCE.md`, section 6).

## Options considered

**Where the books live**

| Option | How it works | For | Against |
|---|---|---|---|
| **A. Recomputed from the decision log every time** | The log is the only truth. Positions, cash and values are worked out afresh from its records. | One truth; nothing can drift apart; the way plain-text accounting programs (Beancount, Ledger) and "event sourcing" work. A full recomputation takes seconds at this size | Needs care that the same records always give the same result |
| B. A small database updated every day | Positions and cash are rows that are changed daily | Easy to query | Two truths (log and database) that can drift apart; a bug changes history unnoticed; against the spec's "nothing is edited" |
| C. A, plus a database that can be thrown away and rebuilt | The log is the truth; a database is a fast copy | Fast for the app | One more part to keep up; not needed yet |

**Value of a share that stops trading for cause** (bankruptcy, removal from the exchange)

| Option | For | Against |
|---|---|---|
| The last price on the exchange | Simple | Flatters: the published studies find that such shares lose about half after the last exchange price |
| **A later price when there is one, otherwise the last price less 55%** | The correction found for Nasdaq shares (Shumway and Warther 1999); index makers use the later price or nearly zero | A rule of thumb |
| Zero | Never flatters | Too harsh as a general rule: many such shares still trade for something |

## Decision

### 1. The books: option A
- The decision log (record 0004), with its private files for prices, is the only truth. Positions, cash and the
  value of every fund are recomputed from it.
- **A fill is written to the log as a fact**: the day, number of shares, price, amount, cost, and the version of
  the rules used. Everything but the day and the rule version is in the sealed part (record 0007, point 6; record
  0004). Recomputing adds facts up; it never works out an old fill again. A later change of the code can therefore
  not change the past.
- Prices for the daily values come only from the saved price files, never from a fresh download.
- A test checks that a full recomputation gives exactly the published values.
- A database copy (option C) is added only if recomputing takes more than about a minute, or when the app needs it.
- Everything is keyed on the SEC company number, never on the ticker (record 0006).
- **The Dice funds** follow completely from the published starting number of the random generator, the covered
  list on the draw day and the prices. The public log holds their starting number and each monthly draw, not a line
  for every one of their trades. **Their daily values are kept in a private file and are never published**: with a
  thousand funds of twenty known companies each, every share's daily price move could be worked back out of them.
  What may be public is each AI fund's place among them, and only after open point 1 of record 0007 is settled.
  The Dice and Rules funds follow the same booking rules as the AI funds: whole shares, the same costs, the same
  wait for a missing price; a monthly draw is an order like any other, made in the first session of the month.

### 2. Booking an order
**The risk limits are checked once, when the decision is made** (spec, section 1, step 6), against the fund as it
is then. An order that passed is not checked against the limits again on the fill day; only the mechanical rules
below can still make it smaller.

In this order, on the fill day (the rules of the spec, made exact):
1. **The price file of that day must be there.** If the morning download failed or has not run, nothing is booked
   and nothing counts as "no price"; the booking waits for the file.
2. Company events of that day are booked first (point 4).
3. The fund's value is taken at the last closing prices before the fill day.
4. An order of "x% of the fund" becomes x% of that value, divided by the opening price, rounded **down** to whole
   shares. A sale of a whole position sells all its shares.
5. Sells are booked, then buys. The cash needed for a buy is its amount plus its trading cost. If cash is short
   after the sells, every buy of that day is cut by the same proportion and rounded down again.
6. The trading cost is charged on the amount of each trade and taken from cash.
7. A trade that ends up smaller than 0.5% of the fund is not made, and the log says so; its cash simply stays in
   the fund. **The sale of a whole position is always made**, however small.
8. A share that has no opening price on the fill day although the price file is there (trading was halted): the
   order waits for the first day with an opening price. After 5 trading days, counted from the day it should have
   been filled, it lapses; the log says so. A new decision about the same company in the same fund replaces a
   waiting order, and the log says that too.

Money is counted in whole cents. Amounts are rounded to the nearest cent; a trading cost is rounded up.

Daily values use closing prices. A share without a price that day keeps its last price, and the value is marked.

### 3. Trading costs
- **Starting figures, as in the spec:** 0.25% above $2 billion market value, 0.5% between $1 and $2 billion, 1.0%
  below $1 billion, on the amount traded, the same for all funds.
- **They are plausible for trades at the opening.** The most recent study of opening and closing auctions (Goyal,
  Jegadeesh and Wu, 2025) finds that the opening is the expensive moment of the day, with costs for small orders in
  small companies around 1% and in larger ones a few tenths of a percent. Figures from large managers that trade
  patiently during the day are much lower and do not apply here.
- **How they are checked before the start.** One pilot week of daily prices cannot measure this: the estimate is
  too noisy. Instead a script estimates the typical gap between buying and selling price from at least a year of
  saved daily prices per size band (the method of Ardia, Guidotti and Kroencke, 2024, made for exactly this kind of
  data), and compares it with the three figures. This uses old prices to set a cost; it does not score any agent.
- The outcome, and the final figures, are added to this record as an update before the funds start. Also decided
  then: whether an order that is large against a share's daily trading (more than 1% of it) gets a surcharge. The
  evidence says the smallest companies and the Bold fund's largest orders are where the starting figures may be
  too low.
- Returns are shown before and after costs (spec).

### 4. Company events, one rule each
Every event is one line in a table of company events, with the link to the SEC filing it comes from. The table is
a file in the data folder that only grows. Share splits (a company replacing each share by several, or several by
one) come from the price service's list and are checked against the filing. Takeovers and the like are rare; a
line for them is added from the filing in a normal working session, outside the daily round, and never by an agent
that manages a fund. **Only the daily script writes to the log:** in step 2 of the next session it reads the new
lines of the table, writes an event record for each and applies it. No portfolio manager can enter or change an
event.

| Event | Rule |
|---|---|
| Share split, either direction | Shares × the ratio. A fraction of a share is paid out in cash at the first opening price after the split, without cost. All prices in the books are the prices as they were traded on the day, not prices that the service has recalculated afterwards for later splits |
| Takeover for cash | Cash at the deal price on the day the deal completes, without trading cost |
| Takeover for shares | Shares of the buyer by the deal's ratio, fraction in cash. If the buyer is not on the covered list (it usually is a large company), the shares are sold at the buyer's next opening price, with the normal cost |
| Mixed deal | The standard terms of the deal; choices offered to shareholders are not modelled |
| Right to a later payment (a "contingent value right", common in biotech takeovers) | Valued at **zero**. If a payment is ever made, it is booked as cash on that day, as a new record |
| Spin-off (part of a company becomes a separate listed company, and shareholders get its shares) | The new shares by the ratio; sold at their first opening price if the new company is not on the covered list; valued at zero if they have not traded within 20 trading days |
| Removal from the exchange for cause, or bankruptcy | Sold at the first price available within 5 trading days after the removal; otherwise at the last price less 55%; zero when the company is wound up with nothing for shareholders |
| New ticker or new name | Nothing is booked; the linking table gets a dated line |

A company that is taken over or removed leaves the universe on that day. Dividends are rare in this universe; a
cash dividend is added to cash on its payment day.

## Differs from the spec
1. Section 4 says company events "are booked by script from SEC filings". Share splits are. For takeovers and the
   like, a line is added to the table by hand from the filing, and the script books it. Reason: the terms of a
   deal cannot be read reliably by a simple program, and there will be only a handful.
2. Section 4 says the Dice funds show "where does each fund fall among 1,000 random ones". The place may be shown
   (after open point 1 of record 0007); the values of the thousand funds themselves stay private.
3. The 0.5% minimum does not apply to selling a whole position.

## Consequences
- The books can be checked by anyone who has the log and the prices; the public can check everything except the
  sealed prices, which they can look up themselves.
- If the private files with prices ever have to be deleted (record 0007), the books can no longer be recomputed;
  the published records stay.
- The check of the trading costs needs a year of past prices; record 0007 fetches that history once.
- Whole shares and rounding down leave a little cash unused; the same for every fund.
- The rules lean to the cautious side on purpose (zero for rights to later payments, a 55% cut for removed shares),
  so that the results are not flattered.
- A takeover premium is booked only when the deal completes; until then the position simply has its market price.
- Company events entered by hand can contain mistakes. Each has its filing link, and a wrong one is corrected by a
  new record, never by editing.
- `docs/research/OPEN-SOURCE.md`, section 6, still says "filled at the next close"; the spec and this record say
  the next opening price.

## Revisit
Revisit: by 2027-02, or before the owner's go for the start of the funds: the trading costs must have been checked
against a year of prices and fixed in an update to this record.

## Sources
Read on 2026-11-17 unless noted.
- Martin Fowler, [Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html)
- [Beancount design](https://beancount.github.io/docs/beancount_design_doc/); [Ledger manual](https://www.ledger-cli.org/3.0/doc/ledger3.html) ("Ledger will never alter your input file")
- Overeem and others, [An Empirical Characterization of Event Sourced Systems and Their Schema Evolution](https://ar5iv.labs.arxiv.org/html/2104.01146) (what practitioners regret)
- Goyal, Jegadeesh and Wu, [price impact in opening and closing auctions](https://jfqa.org/wp-content/uploads/2026/01/25551_Price_Impact.pdf), Journal of Financial and Quantitative Analysis, 2025
- Ardia, Guidotti and Kroencke, [Efficient estimation of bid-ask spreads from open, high, low, and close prices](https://irf.fhnw.ch/bitstreams/e8c469d2-9c64-4004-8e87-53ee091f0cb1/download), Journal of Financial Economics, 2024
- FTSE Russell, [Corporate Actions and Events Guide](https://www.lseg.com/content/dam/ftse-russell/en_us/documents/policy-documents/corporate-actions-and-events-guide.pdf)
- S&P Dow Jones Indices, [pricing of bankrupt US-listed securities](https://press.spglobal.com/2017-07-31-S-P-Dow-Jones-Indices-Announces-Changes-to-the-S-P-U-S-Indices-Methodology-and-to-the-Pricing-of-Bankrupt-U-S-Listed-Securities)
- Shumway and Warther, [The Delisting Bias in CRSP's Nasdaq Data](https://ideas.repec.org/a/bla/jfinan/v54y1999i6p2361-2379.html), Journal of Finance, 1999 (summary read)
- Rights to later payments in life-science takeovers: [Harvard Law School Forum](https://corpgov.law.harvard.edu/2023/06/16/key-components-and-trends-of-cvrs-in-life-sciences-public-ma-deals/), [BioCentury](https://www.biocentury.com/article/655376/cvrs-heavily-discounted-in-biopharma-m-a-deals-data-byte)
- Earlier research: `docs/research/OPEN-SOURCE.md`, section 6

Not verified: the cost figures of large managers (Frazzini, Israel and Moskowitz) were seen in summaries only;
S&P's full rule book on company events could not be opened; whether the price service still gives a price for a
share after its removal from the exchange.
