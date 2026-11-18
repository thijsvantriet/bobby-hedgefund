from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

from bobby_hedgefund.archive.store import sha256_hex
from bobby_hedgefund.funds import orders
from bobby_hedgefund.session import answers, marker, roles, tasks

REPO = Path(__file__).resolve().parents[1]
AGENTS = REPO / ".claude" / "agents"
HOOKS = REPO / ".claude" / "hooks" / "bobby_hooks.py"
DOCUMENTED = {"name", "description", "tools", "disallowedTools", "model", "effort", "permissionMode", "maxTurns", "skills", "mcpServers", "hooks", "memory", "background", "omitClaudeMd", "isolation", "color"}  # fmt: skip  # noqa: E501


def front(text: str) -> tuple[dict[str, str], str]:
    """The top-level fields of an agent file's header, and its body."""
    assert text.startswith("---\n")
    head, body = text[4:].split("\n---\n", 1)
    fields = {}
    for line in head.splitlines():
        if line and not line.startswith(" "):
            key, _, value = line.partition(":")
            fields[key] = value.strip()
    return fields, body


# ---------------------------------------------------------------- the agent files


def test_the_agent_files_are_exactly_what_the_role_table_says() -> None:
    assert sorted(p.name for p in AGENTS.iterdir()) == sorted(role.file for role in roles.ROLES)
    for role in roles.ROLES:
        text = (AGENTS / role.file).read_text(encoding="utf-8")
        assert text == roles.render(role), f"{role.file} differs from the role table: run roles.write_files"
        # The fingerprint the log records for an agent file is the fingerprint of exactly this text.
        assert sha256_hex((AGENTS / role.file).read_bytes()) == sha256_hex(roles.render(role).encode("utf-8"))


@pytest.mark.parametrize("role", roles.ROLES, ids=lambda r: r.name)
def test_every_agent_can_only_read_files_and_has_its_model_and_effort_fixed(role: roles.Role) -> None:
    fields, body = front((AGENTS / role.file).read_text(encoding="utf-8"))
    assert set(fields) <= DOCUMENTED and set(fields) == set(
        roles.ALLOWED_FIELDS
    )  # a misspelt field is ignored silently
    assert fields["name"] == role.name == role.file.removesuffix(".md") and role.name.startswith("bobby-")
    assert fields["tools"] == "Read, Grep, Glob"  # no command line, no web, no way to start another agent
    for forbidden in ("Bash", "Web", "Agent", "Write", "Edit", "mcp", "Skill"):
        assert forbidden not in fields["tools"]
    assert re.fullmatch(r"claude-(haiku|opus|fable)-\d+-\d+", fields["model"])  # a full name, never "opus" or "inherit"
    assert fields["effort"] in ("low", "medium", "high", "xhigh", "max")
    assert fields["omitClaudeMd"] == "true"
    text = (AGENTS / role.file).read_text(encoding="utf-8")
    assert ".claude/hooks/bobby_hooks.py fence" in text and 'matcher: "*"' in text  # the reading check, on every tool
    assert roles.COMMON in body and body.count("```json") == 2 and "## The form of your answer" in body
    assert "paper money" in body and "cannot look anything up" in body and "No share price" in body


def test_the_models_and_efforts_are_those_of_the_spec() -> None:
    by = roles.BY_NAME
    assert (by["bobby-screening"].model, by["bobby-screening"].effort) == ("claude-haiku-5-5", "low")
    analysts = [n for n in by if n.endswith("-analyst")] + ["bobby-results-reader", "bobby-bull", "bobby-bear"]
    assert len(analysts) == 7 and all((by[n].model, by[n].effort) == ("claude-opus-5-5", "high") for n in analysts)
    managers = [n for n in by if n.startswith("bobby-pm-")]
    assert managers == ["bobby-pm-careful", "bobby-pm-bold", "bobby-pm-debate"]
    assert all((by[n].model, by[n].effort) == ("claude-fable-5-2", "high") for n in managers)
    assert by["bobby-screening-check"].model == "claude-opus-5-5"
    assert roles.NEXT_DOWN == {"claude-fable-5-2": "claude-opus-5-5", "claude-opus-5-5": "claude-sonnet-5-5"}


def test_a_manager_is_told_the_limits_the_code_enforces() -> None:
    for fund in ("careful", "bold", "debate"):
        per_stock, risky = orders.LIMITS[fund]
        body = roles.BY_NAME[f"bobby-pm-{fund}"].body
        assert f"At most {per_stock * 100:.0f}% of the fund in one stock" in body
        assert (
            f"at most {risky} positions with a make-or-break" in body
            and f"at most {orders.MAX_POSITIONS} positions" in body
        )
    assert "bull and the bear case" in roles.BY_NAME["bobby-pm-debate"].body
    assert "bull and the bear case" not in roles.BY_NAME["bobby-pm-careful"].body


def test_the_example_in_every_agent_file_is_an_answer_the_script_accepts() -> None:
    for role in roles.ROLES:
        example = re.search(r"```json\n(.*?)\n```", role.body, re.DOTALL)
        assert example, role.name
        answers.parse("My answer.\n\n```json\n" + example.group(1) + "\n```\n", role.answer)
    extra = '"resolved": [{"forecast": 123, "result": "yes", "resolved_on": "2027-05-20", "summary": "One.", "sources": [12]}]'  # noqa: E501
    assert extra.replace('"One."', '"One sentence."') in roles.BY_NAME["bobby-clinical-analyst"].body.replace("\n ", "")


# ---------------------------------------------------------------- the checks Claude Code runs, on recorded input


def hook(name: str, event: dict | str, data: Path) -> tuple[int, str]:
    text = event if isinstance(event, str) else json.dumps(event)
    done = subprocess.run([sys.executable, str(HOOKS), name], input=text, capture_output=True, text=True, env={"BOBBY_DATA_DIR": str(data), "PATH": "/usr/bin:/bin"}, check=False)  # fmt: skip  # noqa: E501
    return done.returncode, done.stderr


@pytest.fixture
def round_(tmp_path: Path) -> dict:
    data = tmp_path / "data"
    session_dir = data / "pilot" / "sessions" / "2027-02-03"
    (session_dir / "companies" / "101").mkdir(parents=True)
    (session_dir / "companies" / "101" / "company.md").write_text("# Aaa\n")
    outside = data / "archive" / "raw" / "later.txt"
    outside.parent.mkdir(parents=True)
    outside.write_text("saved after the cut-off\n")
    (session_dir / "companies" / "101" / "peek.md").symlink_to(outside)
    (session_dir / "way-out").symlink_to(data / "archive")
    round_dir = data / "pilot" / "rounds" / "2027-02-03"
    marker.write(data, session_id="session-1", session_dir=session_dir, round_dir=round_dir, mode="pilot")
    return {"data": data, "session_dir": session_dir, "round_dir": round_dir, "outside": outside}


def read(path: Path | str, **more) -> dict:
    return {"tool_name": "Read", "tool_input": {"file_path": str(path)}, "agent_type": "bobby-science-analyst", "session_id": "session-1", "cwd": str(REPO), **more}  # fmt: skip  # noqa: E501


def test_the_marker_and_the_checks_agree_on_what_an_active_round_is() -> None:
    source = HOOKS.read_text()
    assert f'MARKER = "{marker.FILE}"' in source and "MAX_AGE_SECONDS = 90 * 60" in source
    assert marker.MAX_AGE_SECONDS == 90 * 60 and HOOKS.stat().st_mode & 0o111  # the checks file can be run


def test_the_project_settings_name_only_checks_that_exist_and_stand_aside_outside_a_round() -> None:
    settings = json.loads((REPO / ".claude" / "settings.json").read_text())
    assert set(settings) == {"hooks"} and set(settings["hooks"]) == {"SessionStart", "PreToolUse"}
    commands = [h["command"] for group in settings["hooks"].values() for entry in group for h in entry["hooks"]]
    names = [c.rsplit(" ", 1)[1] for c in commands]
    assert sorted(names) == ["agent-start", "no-edits", "session-start"]  # the fence is named in the agent files only
    assert all(c.startswith('"${CLAUDE_PROJECT_DIR}"/.claude/hooks/bobby_hooks.py ') for c in commands)
    source = HOOKS.read_text()
    assert all(f'"{name}"' in source for name in names)
    matchers = [entry.get("matcher") for entry in settings["hooks"]["PreToolUse"]]
    assert matchers == ["Agent", "Write|Edit|NotebookEdit|MultiEdit"]  # never the command line or reading


def test_an_agent_reads_inside_the_session_folder_and_nowhere_else(round_: dict) -> None:
    data, folder = round_["data"], round_["session_dir"]
    assert hook("fence", read(folder / "companies" / "101" / "company.md"), data) == (0, "")
    assert (
        hook(
            "fence", {**read(""), "tool_name": "Grep", "tool_input": {"pattern": "endpoint", "path": str(folder)}}, data
        )[0]
        == 0
    )
    assert (
        hook(
            "fence",
            {**read(""), "tool_name": "Glob", "tool_input": {"pattern": "**/*.md", "path": str(folder / "companies")}},
            data,
        )[0]
        == 0
    )
    refused = {
        "a file saved after the cut-off, in the archive": read(round_["outside"]),
        "a link that leads out": read(folder / "companies" / "101" / "peek.md"),
        "a folder link that leads out": read(folder / "way-out" / "raw" / "later.txt"),
        "dots that lead out": read(folder / ".." / ".." / ".." / "archive" / "raw" / "later.txt"),
        "the settings with the keys": read(REPO / ".env"),
        "a path that is not absolute": read("README.md"),
        "the private list of names": read(data / "pilot" / "private-names.tsv"),
        "a search without a folder": {**read(""), "tool_name": "Grep", "tool_input": {"pattern": "x"}},
        "a search in the whole data folder": {
            **read(""),
            "tool_name": "Grep",
            "tool_input": {"pattern": "x", "path": str(data)},
        },
        "a search pattern that leaves its folder": {
            **read(""),
            "tool_name": "Glob",
            "tool_input": {"pattern": "../../**", "path": str(folder)},
        },
        "an absolute search pattern": {
            **read(""),
            "tool_name": "Glob",
            "tool_input": {"pattern": "/etc/*", "path": str(folder)},
        },
        "the command line": {**read(""), "tool_name": "Bash", "tool_input": {"command": "curl example.org"}},
        "a web tool": {**read(""), "tool_name": "WebFetch", "tool_input": {"url": "https://example.org"}},
        "starting another agent": {**read(""), "tool_name": "Agent", "tool_input": {"prompt": "x"}},
    }
    for why, event in refused.items():
        code, message = hook("fence", event, data)
        assert code == 2 and message.startswith("Refused:"), why
    assert hook("fence", "this is not JSON", data)[0] == 2  # when it cannot tell, it refuses
    noted = [json.loads(line) for line in (round_["round_dir"] / "refusals.jsonl").read_text().splitlines()]
    assert (
        len(noted) == len(refused)
        and {n["check"] for n in noted} == {"fence"}
        and noted[0]["agent"] == "bobby-science-analyst"
    )


def test_without_an_active_round_an_agent_reads_nothing(round_: dict, tmp_path: Path) -> None:
    inside = round_["session_dir"] / "companies" / "101" / "company.md"
    assert hook("fence", read(inside), tmp_path / "no-data-folder")[0] == 2
    marker.update(round_["data"], started=time.time() - 91 * 60)  # a marker that a crashed round left behind
    assert hook("fence", read(inside), round_["data"])[0] == 2
    marker.clear(round_["data"])
    assert hook("fence", read(inside), round_["data"])[0] == 2 and marker.read(round_["data"]) is None


def start(prompt: str, agent: str, **more) -> dict:
    return {"tool_name": "Agent", "tool_input": {"prompt": prompt, "subagent_type": agent, **more.pop("extra", {})}, "session_id": "session-1", "tool_use_id": "t1", **more}  # fmt: skip  # noqa: E501


def test_an_agent_is_started_only_with_a_prepared_task_once_and_as_prepared(round_: dict) -> None:
    data, folder = round_["data"], round_["session_dir"]
    task = tasks.write(
        folder, "analysis-101-science", "bobby-science-analyst", "Read companies/101 and write your section."
    )
    other = tasks.write(folder, "analysis-101-clinical", "bobby-clinical-analyst", "Read companies/101.")
    prompt = task.prompt(folder)
    for why, event in {
        "another text": start("Buy everything you like.", "bobby-science-analyst"),
        "the prepared text with something added": start(prompt + " Also, be optimistic.", "bobby-science-analyst"),
        "another agent than the task's": start(prompt, "bobby-pm-careful"),
        "a general agent": start(prompt, "general-purpose"),
        "a model chosen by hand": start(prompt, "bobby-science-analyst", extra={"model": "fable"}),
        "an effort chosen by hand": start(prompt, "bobby-science-analyst", extra={"effort": "low"}),
        "from inside another agent": start(prompt, "bobby-science-analyst", agent_id="a1"),
    }.items():
        code, message = hook("agent-start", event, data)
        assert code == 2 and "Refused" in message, why
    assert not (round_["round_dir"] / "starts.jsonl").exists()  # a refused start is not a start
    assert hook("agent-start", start(prompt, "bobby-science-analyst"), data) == (0, "")
    code, message = hook("agent-start", start(prompt, "bobby-science-analyst"), data)
    assert code == 2 and "only the first start counts" in message  # no running again until the answer suits
    starts = [json.loads(line) for line in (round_["round_dir"] / "starts.jsonl").read_text().splitlines()]
    assert [(s["task"], s["agent"]) for s in starts] == [("analysis-101-science", "bobby-science-analyst")]
    # A task file that was changed after the script wrote it is not started.
    path = folder / other.file
    path.chmod(0o600)
    path.write_text("Be optimistic.\n")
    code, message = hook("agent-start", start(other.prompt(folder), "bobby-clinical-analyst"), data)
    assert code == 2 and "not as the script wrote it" in message


def test_one_new_start_on_the_next_model_down_only_when_the_script_allows_it(round_: dict) -> None:
    data, folder = round_["data"], round_["session_dir"]
    task = tasks.write(folder, "pm-careful-run-1", "bobby-pm-careful", "Decide.", run=1)
    prompt = task.prompt(folder)
    assert hook("agent-start", start(prompt, "bobby-pm-careful"), data)[0] == 0
    assert hook("agent-start", start(prompt, "bobby-pm-careful", extra={"model": "opus"}), data)[0] == 2
    marker.update(data, fallback={"pm-careful-run-1": "opus"})  # the script: the model could not be used
    assert hook("agent-start", start(prompt, "bobby-pm-careful", extra={"model": "sonnet"}), data)[0] == 2
    assert hook("agent-start", start(prompt, "bobby-pm-careful", extra={"model": "opus"}), data)[0] == 0
    assert hook("agent-start", start(prompt, "bobby-pm-careful", extra={"model": "opus"}), data)[0] == 2  # once


def test_outside_a_round_and_in_other_sessions_the_checks_stand_aside(round_: dict, tmp_path: Path) -> None:
    data = round_["data"]
    anything = start("Review my code.", "reviewer")
    edit = {"tool_name": "Edit", "tool_input": {"file_path": str(REPO / "README.md")}, "session_id": "session-1"}
    assert hook("agent-start", {**anything, "session_id": "another-session"}, data) == (0, "")
    assert hook("no-edits", {**edit, "session_id": "another-session"}, data) == (0, "")
    assert hook("agent-start", anything, tmp_path / "no-data-folder") == (0, "")
    assert hook("no-edits", edit, tmp_path / "no-data-folder") == (0, "")
    marker.clear(data)
    assert hook("agent-start", anything, data) == (0, "") and hook("no-edits", edit, data) == (0, "")
    assert hook("agent-start", "this is not JSON", data)[0] == 0 and hook("nonsense", anything, data)[0] == 0


def test_while_a_round_is_active_the_leading_session_changes_no_files(round_: dict) -> None:
    data = round_["data"]
    for tool in ("Write", "Edit", "NotebookEdit"):
        code, message = hook("no-edits", {"tool_name": tool, "tool_input": {}, "session_id": "session-1"}, data)
        assert code == 2 and "bobby-session end" in message
    assert hook("no-edits", {"tool_name": "Bash", "tool_input": {}, "session_id": "session-1"}, data)[0] == 0


def test_how_a_session_began_is_noted_and_never_gets_in_the_way(tmp_path: Path) -> None:
    data = tmp_path / "data"
    event = {
        "session_id": "abc-123",
        "source": "clear",
        "transcript_path": "/x/abc-123.jsonl",
        "hook_event_name": "SessionStart",
    }
    assert hook("session-start", event, data) == (0, "")
    assert hook("session-start", {**event, "source": "resume"}, data) == (0, "")
    noted = [json.loads(line) for line in (data / "claude-sessions" / "abc-123.jsonl").read_text().splitlines()]
    assert [n["source"] for n in noted] == ["clear", "resume"]
    assert hook("session-start", {**event, "session_id": "../../escape"}, data) == (0, "")
    assert not (tmp_path / "escape.jsonl").exists() and len(list((data / "claude-sessions").iterdir())) == 1
    blocked = tmp_path / "a-file"
    blocked.write_text("x")
    assert hook("session-start", event, blocked) == (0, "")  # a data folder that cannot be written: still no error


def test_a_stand_in_is_started_exactly_as_the_script_prepared_it(round_: dict) -> None:
    data, folder = round_["data"], round_["session_dir"]
    task = tasks.write(
        folder, "analysis-101-science", "bobby-science-analyst", "The role's instructions, then the task."
    )
    index = folder / "tasks" / "index.jsonl"
    line = json.loads(index.read_text())
    line["stand_in"] = {"subagent_type": "general-purpose", "model": "opus", "effort": "high"}
    index.write_text(json.dumps(line) + "\n")
    prompt = task.prompt(folder)
    assert hook("agent-start", start(prompt, "bobby-science-analyst"), data)[0] == 2  # the agent file is not loaded
    assert (
        hook("agent-start", start(prompt, "general-purpose", extra={"model": "fable", "effort": "high"}), data)[0] == 2
    )
    assert (
        hook("agent-start", start(prompt, "general-purpose", extra={"model": "opus", "effort": "high"}), data)[0] == 0
    )


# ---------------------------------------------------------------- answers


def wrap(found: dict) -> str:
    return "Here is my answer.\n\n```json\n" + json.dumps(found, indent=1) + "\n```\n"


DECISIONS = {
    "fund": "careful",
    "decisions": [
        {
            "cik": 101,
            "action": "buy",
            "size_pct": "3%",
            "thesis": {
                "claim": "c",
                "edge": "e",
                "catalyst": "k",
                "catalyst_date": "2027-06-01",
                "probability": "60%",
                "risks": "r",
                "sell_if": "s",
            },
            "sources": [{"n": 12, "summary": "s"}],
        },
        {"cik": 102, "action": "sell", "reason": "The sell rule was met.", "sources": []},
    ],
    "lacked": ["the full results"],
}


def test_an_answer_in_its_form_is_read() -> None:
    assert answers.parse(wrap(DECISIONS), "decisions") == DECISIONS
    assert answers.parse(wrap({"fund": "bold", "decisions": [], "lacked": []}), "decisions")["decisions"] == []
    screening = {
        "companies": [{"cik": 101, "deep_look": True, "urgent": False, "why": "A results announcement."}],
        "lacked": [],
    }
    assert answers.parse(wrap(screening), "screening") == screening


def change(found: dict, path: str, value: object) -> dict:
    copy = json.loads(json.dumps(found))
    target = copy
    parts = path.split("/")
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    if value is ...:
        del target[parts[-1]]
    else:
        target[parts[-1]] = value
    return copy


@pytest.mark.parametrize(
    "text",
    [
        "No block at all.",
        wrap(DECISIONS) + wrap(DECISIONS),
        wrap(DECISIONS) + "\nOne more thought: buy more.",
        "```json\n{not json}\n```\n",
        "```json\n[1, 2]\n```\n",
        wrap(change(DECISIONS, "decisions/0/size_pct", 3)),
        wrap(change(DECISIONS, "decisions/0/size_pct", "3")),
        wrap(DECISIONS).replace('"3%"', "0.03"),
        wrap(change(DECISIONS, "decisions/0/thesis", ...)),
        wrap(change(DECISIONS, "decisions/0/size_pct", ...)),
        wrap(change(DECISIONS, "decisions/0/thesis/probability", "160%")),
        wrap(change(DECISIONS, "decisions/0/thesis/sell_if", "")),
        wrap(change(DECISIONS, "decisions/1/reason", ...)),
        wrap(change(DECISIONS, "decisions/1/cik", 101)),
        wrap(change(DECISIONS, "decisions/1/action", "short")),
        wrap(change(DECISIONS, "fund", "dice")),
        wrap(change(DECISIONS, "confidence", "high")),
        wrap(change(DECISIONS, "decisions", [DECISIONS["decisions"][1] | {"cik": 200 + i} for i in range(6)])),
    ],
)
def test_an_answer_that_is_not_in_its_form_is_thrown_away(text: str) -> None:
    with pytest.raises(answers.AnswerError) as refused:
        answers.parse(text, "decisions")
    assert "sell rule was met" not in str(refused.value)  # the message says what is wrong, not what was said


def test_a_section_with_forecasts_and_resolved_ones() -> None:
    section = {
        "cik": 101,
        "section": "The trial is well designed.",
        "forecasts": [
            {
                "event": "The main goal of trial NCT01234567 is met",
                "event_kind": "trial result",
                "by_date": "2027-06-01",
                "probability": "60%",
                "make_or_break": True,
                "reasoning": "Why.",
                "sources": [12],
            }
        ],
        "resolved": [{"forecast": 7, "result": "yes", "resolved_on": "2027-02-02", "summary": "Met.", "sources": [12]}],
        "sources": [{"n": 12, "summary": "The registry record."}],
        "lacked": [],
    }
    assert answers.parse(wrap(section), "section")["forecasts"][0]["probability"] == "60%"
    for path, value in (
        ("forecasts/0/by_date", "June"),
        ("forecasts/0/event_kind", "price"),
        ("resolved/0/result", "maybe"),
        ("cik", "101"),
    ):
        with pytest.raises(answers.AnswerError):
            answers.parse(wrap(change(section, path, value)), "section")
    with pytest.raises(answers.AnswerError, match="unknown kind"):
        answers.parse(wrap(section), "poem")
