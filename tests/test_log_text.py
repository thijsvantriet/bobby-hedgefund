from __future__ import annotations

from pathlib import Path

import pytest
from logkit import DAY1, clock, decision, forecast, lines, make_log

from bobby_hedgefund.log import text as T

SOURCE = (
    "The primary endpoint of the phase 3 trial was met with a statistically significant improvement in overall "
    "survival compared with placebo in the intention to treat population, and the safety profile was consistent "
    "with earlier studies of the drug in this indication across all dose groups tested so far. "
    "Secondary endpoints will be reported at a medical meeting later this year together with the full data set."
)
WORDS = SOURCE.split()
# A made-up address to test the removal of addresses. Put together here, so that no file of this public repository
# holds anything that looks like a real one.
ADDRESS = "someone" + "@" + "example.org"


def quote(n: int, start: int = 0) -> str:
    return " ".join(WORDS[start : start + n])


def cleaned(text: str, known: set[int] | None = None) -> T.Cleaned:
    return T.clean(text, T.find_copies([text], [SOURCE])[0], known)


def test_a_copied_run_is_found_whatever_the_capitals_and_punctuation() -> None:
    text = "Our view: " + quote(20).upper().replace(" ", ",  ") + " and that is good."
    (copies,) = T.find_copies([text], ["some other file", SOURCE])
    assert [c.words for c in copies] == [20]
    assert T.find_copies(["nothing copied here at all, just our own short words"], [SOURCE]) == [[]]
    assert T.find_copies([quote(7)], [SOURCE]) == [[]]  # shorter than the window: not looked at


def test_more_than_forty_copied_words_is_a_long_quote_and_goes() -> None:
    assert cleaned("We read: " + quote(40) + ". Fine.").removed == []
    result = cleaned("We read: " + quote(41) + ". Fine.")
    assert result.text == "We read: [removed]. Fine."
    assert [(s.why, s.keep, len(s.content.split())) for s in result.removed] == [("quote", True, 41)]


def test_two_short_quotes_are_allowed_a_third_goes() -> None:
    a, b, c = quote(16, 0), quote(16, 18), quote(16, 36)
    assert cleaned(f"One: {a}. Our words in between. Two: {b}. Done.").removed == []
    result = cleaned(f"One: {a}. Our words in between. Two: {b}. More of our own words. Three: {c}. Done.")
    assert result.text.endswith("Three: [removed]. Done.") and len(result.removed) == 1
    assert cleaned(f"One: {quote(15)}. Two: {quote(15, 18)}. Three: {quote(15, 36)}.").removed == []


@pytest.mark.parametrize(
    "sentence",
    [
        "The shares fell 40% after the news.",
        "It trades below its cash.",
        "The market value is $900 million.",
        "Cash is 1.5x the market capitalisation.",
        "Cash per share is $4.20.",
        "The stock has doubled since the readout.",
        "Shares are up by half this year.",
        "At a share price of 12 dollars the company is cheap.",
        "The valuation leaves room.",
        "The stock closed at 7.",
    ],
)
def test_a_sentence_about_a_price_or_worked_out_from_one_is_sealed_whole(sentence: str) -> None:
    result = cleaned(f"The trial is well designed. {sentence} The readout is due in May.")
    assert result.text == "The trial is well designed. [sealed] The readout is due in May."
    assert [(s.why, s.content) for s in result.removed] == [("price", sentence)]


@pytest.mark.parametrize(
    "sentence",
    [
        "The response rate rose from 20% to 45%.",
        "The company shares the rights with a partner.",
        "Enrolment is up to 300 patients.",
        "The main goal was met in the second study.",
        "Half of the patients responded.",
    ],
)
def test_ordinary_sentences_are_left_alone(sentence: str) -> None:
    assert cleaned(sentence).text == sentence


def test_an_amount_of_money_is_sealed_unless_a_filing_states_it() -> None:
    known = T.amounts(
        "Cash and equivalents were $245.3 million; we borrowed USD 50,000,000 and paid 12 million dollars."
    )
    assert known == {245_300_000, 50_000_000, 12_000_000}
    text = "Cash was $245.3 million and the loan is $50 million. A milestone of $75 million follows."
    result = cleaned(text, known)
    assert result.text == "Cash was $245.3 million and the loan is $50 million. A milestone of [sealed] follows."
    assert [(s.why, s.content) for s in result.removed] == [("money", "$75 million")]
    assert cleaned(text).text.count("[sealed]") == 3  # without a filing to trace to, every amount goes
    # A per-share figure goes even when a filing states the amount.
    assert cleaned("The offering was priced at $245.3 million.", known).text == "[sealed]"


def test_keys_addresses_and_home_paths_are_removed_and_kept_nowhere() -> None:
    key = "sk_live_" + "a1B2c3D4" * 5
    text = f"Write to {ADDRESS} with key {key} from /home/somebody/notes.txt on 192.168.1.20 today."
    result = cleaned(text)
    assert result.text == "Write to [removed] with key [removed] from [removed] on [removed] today."
    assert all(s.why == "secret" and s.keep is False for s in result.removed) and len(result.removed) == 4


def test_a_forecast_defined_by_a_price_is_refused() -> None:
    for event in (
        "The share price is above 20 dollars on 1 June",
        "The stock doubles before year end",
        "Market value above 2 billion by June",
        "Shares trade higher after the readout",
    ):
        assert T.price_defined(event), event
    for event in (
        "The main goal of trial X is met, announced before 1 June",
        "The FDA approves the drug by its decision date",
        "The company announces a share sale before 1 June",
    ):
        assert not T.price_defined(event), event
    with pytest.raises(ValueError, match="defined by a price"):
        T.TextCheck().clean_body("forecast", {**forecast(), "event": "The share price is above 20 dollars on 1 June"})


def test_a_decision_is_cleaned_before_it_is_written_and_its_decision_fields_are_not_touched(tmp_path: Path) -> None:
    body = decision(size="3%")
    body["thesis"]["edge"] = "We read: " + quote(45) + " That is why."
    body["thesis"]["risks"] = "A loan of $75 million comes due. The shares fell 40% last month."
    body["saw"] = [{"n": 1, "source": "event report", "summary": "Our summary. It trades below its cash."}]
    before = {k: body[k] for k in ("fund", "action", "size_pct", "fill_rule")} | {"company": dict(body["company"])}
    check = T.TextCheck([SOURCE], set())
    check.clean_body("decision", body)
    assert {k: body[k] for k in before} == before
    assert body["thesis"]["edge"] == "We read: [removed] That is why."
    assert body["thesis"]["risks"] == "A loan of [sealed] comes due. [sealed]"
    assert body["saw"][0]["summary"] == "Our summary. [sealed]"
    assert sorted(s.why for s in body["removed"]) == ["money", "price", "price", "quote"]
    log = make_log(tmp_path)
    with log.writer(DAY1, clock()) as w:
        entry = w.add("decision", body)
    public = b"".join(lines(log))
    for secret in (b"statistically significant", b"75 million", b"fell 40%", b"below its cash"):
        assert secret not in public
    assert len(entry.record["removed"]) == 4 and not log.verify().problems
    opened = log.opened(entry)
    assert "$75 million" in opened["removed"] and "The shares fell 40% last month." in opened["removed"]


def test_overlapping_findings_are_joined_and_counted_once() -> None:
    text = f"The stock closed at $7 on {ADDRESS}'s desk."
    result = cleaned(text)
    assert result.text == "[sealed]" and len(result.removed) == 1
    assert result.removed[0].keep is False  # it holds an address: kept nowhere
