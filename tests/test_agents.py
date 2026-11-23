from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

import pytest

from bobby_hedgefund.archive.store import sha256_hex
from bobby_hedgefund.funds import orders
from bobby_hedgefund.session import answers, marker, roles, tasks

REPO = Path(__file__).resolve().parents[1]
AGENTS = REPO / ".claude" / "agents"
HOOKS = REPO / ".claude" / "hooks" / "bobby_hooks.py"
DOCUMENTED = {"name", "description", "tools", "disallowedTools", "model", "effort", "permissionMode", "maxTurns", "skills", "mcpServers", "hooks", "memory", "background", "omitClaudeMd", "isolation", "color"}  # fmt: skip


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
    assert f"command: '{roles.FENCE}'" in text and 'matcher: "*"' in text  # the reading check, on every tool
    assert roles.COMMON in body and body.count("```json") == 3 and "## The form of your answer" in body
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
    assert '"resolved": [{"forecast": 123' in roles.BY_NAME["bobby-clinical-analyst"].body
    reader = roles.BY_NAME["bobby-results-reader"].body
    assert "You give no forecasts." in reader and '"forecasts"' not in reader  # it has no field for one


# ---------------------------------------------------------------- the checks Claude Code runs, on recorded input


def hook(name: str, event: dict | str, data: Path) -> tuple[int, str]:
    """Run a check exactly as the settings and the agent files name it: through a shell, with the project folder
    in the environment."""
    text = event if isinstance(event, str) else json.dumps(event)
    command = f'python3 "${{CLAUDE_PROJECT_DIR}}/.claude/hooks/bobby_hooks.py" {name}'
    env = {"BOBBY_DATA_DIR": str(data), "PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(REPO)}
    done = subprocess.run(command, shell=True, input=text, capture_output=True, text=True, env=env, check=False)
    return done.returncode, done.stderr


@pytest.fixture
def round_(tmp_path: Path) -> dict:
    data = tmp_path / "data"
    session_dir = data / "pilot" / "sessions" / "2027-02-03"
    (session_dir / "companies" / "101").mkdir(parents=True)
    (session_dir / "companies" / "101" / "company.md").write_text("# Aaa\n")
    for name in ("careful", "bold"):
        (session_dir / "round" / "funds").mkdir(parents=True, exist_ok=True)
        (session_dir / "round" / "funds" / f"{name}.md").write_text("holdings\n")
    (session_dir / "round" / "debate").mkdir()
    (session_dir / "round" / "debate" / "101-bull.md").write_text("case\n")
    (session_dir / "round" / "reports").mkdir()
    (session_dir / "round" / "reports" / "101.md").write_text("report\n")
    outside = data / "archive" / "raw" / "later.txt"
    outside.parent.mkdir(parents=True)
    outside.write_text("saved after the cut-off\n")
    (session_dir / "companies" / "101" / "peek.md").symlink_to(outside)
    (session_dir / "way-out").symlink_to(data / "archive")
    round_dir = data / "pilot" / "rounds" / "2027-02-03"
    marker.write(data, session_id="session-1", session_dir=session_dir, round_dir=round_dir, mode="pilot")
    return {"data": data, "session_dir": session_dir, "round_dir": round_dir, "outside": outside}


def use(tool: str, agent: str = "bobby-science-analyst", **given) -> dict:
    return {"tool_name": tool, "tool_input": given, "agent_type": agent, "session_id": "session-1", "cwd": str(REPO)}


def read(path: Path | str, agent: str = "bobby-science-analyst") -> dict:
    return use("Read", agent, file_path=str(path))


def test_the_marker_and_the_checks_agree_on_what_an_active_round_is(tmp_path: Path) -> None:
    source = HOOKS.read_text()
    assert f'MARKER = "{marker.FILE}"' in source and "MAX_AGE_SECONDS = 90 * 60" in source
    assert marker.MAX_AGE_SECONDS == 90 * 60
    # A marker that is too old, dated in the future or not a number counts as no round, for both.
    for started in (time.time() - 91 * 60, time.time() + 3600, float("nan"), 1e300, "soon"):
        marker.write(tmp_path, session_id="s", session_dir=tmp_path, round_dir=tmp_path, mode="pilot")
        marker.update(tmp_path, started=started)
        assert marker.read(tmp_path) is None, started
        edit = {"tool_name": "Edit", "tool_input": {}, "session_id": "s"}
        assert hook("no-edits", edit, tmp_path) == (0, ""), started  # never switched on for good


def test_the_project_settings_name_only_checks_that_exist_and_never_touch_reading() -> None:
    settings = json.loads((REPO / ".claude" / "settings.json").read_text())
    assert set(settings) == {"hooks", "statusLine"} and set(settings["hooks"]) == {"SessionStart", "PreToolUse"}
    # The status line only shows and saves the usage figures (README, "The daily round"); it is no check.
    assert settings["statusLine"] == {
        "type": "command",
        "command": 'python3 "${CLAUDE_PROJECT_DIR}/.claude/statusline.py"',
    }
    commands = [h["command"] for group in settings["hooks"].values() for entry in group for h in entry["hooks"]]
    names = [c.rsplit(" ", 1)[1] for c in commands]
    # The fence is named in the agent files only.
    assert sorted(names) == ["agent-start", "hands-off", "no-edits", "round-commands", "session-start"]
    assert all(c.startswith('python3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/bobby_hooks.py" ') for c in commands)
    source = HOOKS.read_text()
    assert all(f'"{name}"' in source for name in names)
    matchers = [entry.get("matcher") for entry in settings["hooks"]["PreToolUse"]]
    assert matchers == ["Agent|Task", "Write|Edit|NotebookEdit|MultiEdit", "SendMessage|TaskStop", "Bash"]


def test_an_agent_reads_inside_the_session_folder_and_nowhere_else(round_: dict) -> None:
    data, folder = round_["data"], round_["session_dir"]
    assert hook("fence", read(folder / "companies" / "101" / "company.md"), data) == (0, "")
    assert hook("fence", use("Grep", pattern="endpoint", path=str(folder / "companies"), glob="*.md"), data)[0] == 0
    assert hook("fence", use("Glob", pattern="**/*.md", path=str(folder / "companies")), data)[0] == 0
    assert hook("fence", use("SubagentHandback", message="my answer"), data) == (0, "")  # how a report is handed back
    in_folder = {**read("companies/101/company.md"), "cwd": str(folder)}
    refused = {
        "a file saved after the cut-off, in the archive": read(round_["outside"]),
        "a link that leads out": read(folder / "companies" / "101" / "peek.md"),
        "a folder link that leads out": read(folder / "way-out" / "raw" / "later.txt"),
        "dots that lead out": read(folder / ".." / ".." / ".." / "archive" / "raw" / "later.txt"),
        "the settings with the keys": read(REPO / ".env"),
        "a path that is not a full path": read("README.md"),
        "a path that is not a full path, even with the session folder as working folder": in_folder,
        "a path that starts at the home folder": read("~/bobby-hedgefund-data/prices/manifest.jsonl"),
        "the private list of names": read(data / "pilot" / "private-names.tsv"),
        "a search without a folder": use("Grep", pattern="x"),
        "a search in the whole data folder": use("Grep", pattern="x", path=str(data)),
        "a search pattern that leaves its folder": use("Glob", pattern="../../**", path=str(folder)),
        "a search pattern with braces": use("Glob", pattern="{..,x}/**", path=str(folder)),
        "an absolute search pattern": use("Glob", pattern="/etc/*", path=str(folder)),
        "a file filter that leaves the folder": use("Grep", pattern="x", path=str(folder), glob="../../*"),
        "the command line": use("Bash", command="curl example.org"),
        "a web tool": use("WebFetch", url="https://example.org"),
        "starting another agent": use("Agent", prompt="x"),
        "changing a file": use("MultiEdit", file_path=str(folder / "companies" / "101" / "company.md")),
    }
    for why, event in refused.items():
        code, message = hook("fence", event, data)
        assert code == 2 and message.startswith("Refused:"), why
    assert hook("fence", "this is not JSON", data)[0] == 2  # when it cannot tell, it refuses
    assert hook("fence", "[1, 2]", data)[0] == 2
    noted = [json.loads(line) for line in (round_["round_dir"] / "refusals.jsonl").read_text().splitlines()]
    assert len(noted) == len(refused) and {n["check"] for n in noted} == {"fence"}


def test_a_search_from_the_top_of_the_session_folder_is_refused_and_never_crashes(round_: dict) -> None:
    # The searches of the first pilot day that broke the check (IndexError): a search with the session folder
    # itself as its folder. From there every search reaches the task files and the funds' files (a Glob pattern
    # without a slash matches at any depth, and Claude Code rewrites patterns that start with folder names), so
    # all of them are refused, with a message that says where to search instead.
    data, folder = round_["data"], round_["session_dir"]
    careful = "bobby-pm-careful"
    allowed = {
        "a Glob in a company folder": use("Glob", pattern="**", path=str(folder / "companies" / "101")),
        "a Glob in the reports": use("Glob", careful, pattern="*.md", path=str(folder / "round" / "reports")),
        "a Grep in all company folders": use("Grep", pattern="101", path=str(folder / "companies")),
    }
    for why, event in allowed.items():
        assert hook("fence", event, data) == (0, ""), why
    top = str(folder)
    refused = {
        "a Grep over the whole folder": use("Grep", pattern="101", path=top),
        "the same, with the folder written with a slash at the end": use("Grep", pattern="101", path=top + "/"),
        "the same, with a dot": use("Grep", pattern="101", path=top + "/."),
        "a Grep with a file filter": use("Grep", pattern="x", path=top, glob="*.md"),
        "a Glob of the top, which matches at any depth": use("Glob", pattern="*", path=top),
        "a Glob of one kind of file": use("Glob", pattern="*.md", path=top),
        "a Glob through every folder": use("Glob", pattern="**/*", path=top),
        "a Glob that starts in a company folder": use("Glob", pattern="companies/101/**", path=top),
        "a Glob that leaves things out": use("Glob", pattern="!(companies)", path=top),
        "a Glob that starts with the folder's own name": use("Glob", pattern=f"{folder.name}/tasks/*", path=top),
        "a Glob that names round/ again from round/": use(
            "Glob", careful, pattern="round/funds/*", path=str(folder / "round")
        ),
        "a Glob of the funds from round/": use("Glob", careful, pattern="funds/*", path=str(folder / "round")),
        "a backslash that hides tasks/": use("Glob", pattern="t\\asks/*", path=str(folder / "companies")),
        "a backslash that hides round/": use("Glob", careful, pattern="r\\ound/funds/*", path=top),
        "a backslash in a file filter": use("Grep", pattern="x", path=str(folder / "companies"), glob="t\\asks/*"),
        "reading the folder itself": read(folder),
    }
    for why, event in refused.items():
        code, message = hook("fence", event, data)
        assert code == 2 and message.startswith("Refused:") and "check failed" not in message, why
    assert "companies/<number>" in hook("fence", use("Glob", pattern="*", path=top), data)[1]  # where to search


def test_what_belongs_to_one_fund_cannot_be_read_by_another(round_: dict) -> None:
    data, folder = round_["data"], round_["session_dir"]
    mine = tasks.write(folder, "pm-careful-run-1", "bobby-pm-careful", "Decide.", run=1)
    theirs = tasks.write(folder, "pm-bold-run-1", "bobby-pm-bold", "Decide.", run=1)
    careful = "bobby-pm-careful"
    assert hook("fence", read(folder / mine.file, careful), data)[0] == 0
    assert hook("fence", read(folder / "round" / "funds" / "careful.md", careful), data)[0] == 0
    assert hook("fence", read(folder / "round" / "reports" / "101.md", careful), data)[0] == 0
    assert hook("fence", use("Glob", careful, pattern="*.md", path=str(folder / "round" / "reports")), data)[0] == 0
    for why, event in {
        "another fund's task file": read(folder / theirs.file, careful),
        "the list of all tasks": read(folder / "tasks" / "index.jsonl", careful),
        "a search through the tasks": use("Grep", careful, pattern="Decide", path=str(folder / "tasks")),
        "another fund's holdings": read(folder / "round" / "funds" / "bold.md", careful),
        "a search through the holdings": use("Grep", careful, pattern="x", path=str(folder / "round" / "funds")),
        "the Debate fund's cases": read(folder / "round" / "debate" / "101-bull.md", careful),
        "a search across everything the round wrote": use("Grep", careful, pattern="x", path=str(folder / "round")),
        "an analyst reading a fund's holdings": read(folder / "round" / "funds" / "careful.md"),
    }.items():
        assert hook("fence", event, data)[0] == 2, why
    assert hook("fence", read(folder / "round" / "debate" / "101-bull.md", "bobby-pm-debate"), data)[0] == 0
    assert hook("fence", read(folder / "round" / "debate" / "101-bull.md", "bobby-bear"), data)[0] == 0


def test_the_fence_refuses_whatever_goes_wrong_inside_it(round_: dict, tmp_path: Path) -> None:
    inside = round_["session_dir"] / "companies" / "101" / "company.md"
    assert hook("fence", read(inside), tmp_path / "no-data-folder")[0] == 2  # no round is active
    marker.update(round_["data"], started=time.time() - 91 * 60)  # a marker that a crashed round left behind
    assert hook("fence", read(inside), round_["data"])[0] == 2
    marker.clear(round_["data"])
    assert hook("fence", read(inside), round_["data"])[0] == 2 and marker.read(round_["data"]) is None
    deep = "[" * 100_000 + "]" * 100_000  # a marker that breaks the reader of the marker itself
    (round_["data"] / marker.FILE).write_text(deep)
    assert hook("fence", read("/etc/hostname"), round_["data"])[0] == 2
    (round_["data"] / marker.FILE).write_text('{"a":' * 5000 + "1" + "}" * 5000)
    assert hook("fence", read("/etc/hostname"), round_["data"])[0] == 2
    # And when the checks file cannot be found at all, python3 itself ends with the refusing code.
    env = {"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(tmp_path / "nowhere")}
    command = 'python3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/bobby_hooks.py" fence'
    assert (
        subprocess.run(command, shell=True, input="{}", capture_output=True, text=True, env=env, check=False).returncode
        == 2
    )


def start(prompt: str, agent: str, extra: dict | None = None, **more) -> dict:
    given = {"prompt": prompt, "subagent_type": agent, **(extra or {})}
    return {"tool_name": "Agent", "tool_input": given, "session_id": "session-1", "tool_use_id": "t1", **more}


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
        "the prepared text with other spacing": start(prompt.replace(" ", "  ", 1), "bobby-science-analyst"),
        "another agent than the task's": start(prompt, "bobby-pm-careful"),
        "a general agent": start(prompt, "general-purpose"),
        "a model chosen by hand": start(prompt, "bobby-science-analyst", {"model": "fable"}),
        "an effort chosen by hand": start(prompt, "bobby-science-analyst", {"effort": "low"}),
        "its own copy of the repository": start(prompt, "bobby-science-analyst", {"isolation": "worktree"}),
        "a name, so that it can be messaged later": start(prompt, "bobby-science-analyst", {"name": "friend"}),
        "from inside another agent": start(prompt, "bobby-science-analyst", agent_id="a1"),
    }.items():
        code, message = hook("agent-start", event, data)
        assert code == 2 and "Refused" in message, why
    assert not (round_["round_dir"] / "starts.jsonl").exists()  # a refused start is not a start
    assert hook(
        "agent-start", start(prompt, "bobby-science-analyst", {"description": "x", "run_in_background": True}), data
    ) == (0, "")
    code, message = hook("agent-start", start(prompt, "bobby-science-analyst"), data)
    assert code == 2 and "only the first start counts" in message  # no running again until the answer suits
    starts = [json.loads(line) for line in (round_["round_dir"] / "starts.jsonl").read_text().splitlines()]
    assert [(s["task"], s["agent"], s["tool_use_id"]) for s in starts] == [
        ("analysis-101-science", "bobby-science-analyst", "t1")
    ]
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
    assert hook("agent-start", start(prompt, "bobby-pm-careful", {"model": "opus"}), data)[0] == 2
    marker.update(data, fallback={"pm-careful-run-1": "opus"})  # the script: the model could not be used
    assert hook("agent-start", start(prompt, "bobby-pm-careful"), data)[0] == 2  # not again on the same model
    assert hook("agent-start", start(prompt, "bobby-pm-careful", {"model": "sonnet"}), data)[0] == 2
    assert hook("agent-start", start(prompt, "bobby-pm-careful", {"model": "opus", "effort": "low"}), data)[0] == 2
    assert hook("agent-start", start(prompt, "bobby-pm-careful", {"model": "opus"}), data)[0] == 0
    assert hook("agent-start", start(prompt, "bobby-pm-careful", {"model": "opus"}), data)[0] == 2  # once


def test_outside_a_round_and_in_other_sessions_the_checks_stand_aside(round_: dict, tmp_path: Path) -> None:
    data = round_["data"]
    events = {
        "agent-start": start("Review my code.", "reviewer"),
        "no-edits": {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(REPO / "README.md")},
            "session_id": "session-1",
        },
        "hands-off": {"tool_name": "SendMessage", "tool_input": {"to": "x"}, "session_id": "session-1"},
        "round-commands": {
            "tool_name": "Bash",
            "tool_input": {"command": "git status && rm -rf build"},
            "session_id": "session-1",
        },
    }
    garbage = [
        "",
        "{",
        "[]",
        '{"session_id": "s"}',
        '{"started": "nan"}',
        '"text"',
        "[" * 100_000,
        '{"a":' * 5000 + "1" + "}" * 5000,
    ]
    for name, event in events.items():
        assert hook(name, {**event, "session_id": "another-session"}, data) == (0, ""), name
        assert hook(name, event, tmp_path / "no-data-folder") == (0, ""), name
        assert hook(name, "this is not JSON", data)[0] == 0, name
        for text in garbage:  # a marker in any broken state, in this very session: no round, so nothing is refused
            (data / marker.FILE).write_text(text)
            assert hook(name, event, data) == (0, ""), (name, text[:20])
        marker.write(
            data, session_id="session-1", session_dir=round_["session_dir"], round_dir=round_["round_dir"], mode="pilot"
        )
    marker.clear(data)
    for name, event in events.items():
        assert hook(name, event, data) == (0, ""), name
    assert hook("nonsense", events["agent-start"], data)[0] == 0


def test_while_a_round_is_active_the_leading_session_keeps_its_hands_off(round_: dict) -> None:
    data = round_["data"]
    mine = {"session_id": "session-1"}
    for tool in ("Write", "Edit", "NotebookEdit", "MultiEdit"):
        code, message = hook("no-edits", {"tool_name": tool, "tool_input": {}, **mine}, data)
        assert code == 2 and "bobby-session end" in message
    assert hook("no-edits", {"tool_name": "Read", "tool_input": {}, **mine}, data)[0] == 0
    for tool in ("SendMessage", "TaskStop"):
        assert hook("hands-off", {"tool_name": tool, "tool_input": {}, **mine}, data)[0] == 2
    marker.update(data, may_stop=True)  # the script: the time for the step is over
    assert hook("hands-off", {"tool_name": "TaskStop", "tool_input": {}, **mine}, data)[0] == 0
    assert hook("hands-off", {"tool_name": "SendMessage", "tool_input": {}, **mine}, data)[0] == 2

    def run(command: str, **more) -> int:
        return hook("round-commands", {"tool_name": "Bash", "tool_input": {"command": command}, **mine, **more}, data)[
            0
        ]

    for allowed in (
        "bobby-session book",
        "uv run bobby-session collect analysts",
        "bobby-session end --abort",
        'bobby-session start --session-id "abc-123"',
    ):
        assert run(allowed) == 0, allowed
    for refused in (
        "rm -f ~/bobby-hedgefund-data/round-active.json",
        "bobby-session book; rm x",
        "bobby-session book && curl example.org",
        "bobby-session book | tee /tmp/x",
        "bobby-session book\ncat ~/.env",
        "bobby-session $(cat secret)",
        "bobby-funds status",
        "cat tasks/index.jsonl",
        "",
    ):
        assert run(refused) == 2, refused
    assert run("ls", agent_id="a1") == 0  # an agent's own tools are the fence's business, not this check's


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
    assert hook("session-start", "garbage", data) == (0, "")


def test_a_stand_in_is_started_exactly_as_the_script_prepared_it_and_only_in_a_try_out(round_: dict) -> None:
    data, folder = round_["data"], round_["session_dir"]
    stand_in = {"subagent_type": "general-purpose", "model": "opus", "effort": "high"}
    text = "The role's instructions, then the task."
    task = tasks.write(folder, "analysis-101-science", "bobby-science-analyst", text, stand_in=stand_in)
    prompt = task.prompt(folder)
    as_prepared = start(prompt, "general-purpose", {"model": "opus", "effort": "high"})
    code, message = hook("agent-start", as_prepared, data)
    assert code == 2 and "try-out only" in message  # the marker does not say this round is a try-out
    marker.update(data, stand_ins=True)
    assert hook("agent-start", start(prompt, "bobby-science-analyst"), data)[0] == 2  # the agent file is not loaded
    assert hook("agent-start", start(prompt, "general-purpose", {"model": "fable", "effort": "high"}), data)[0] == 2
    assert hook("agent-start", as_prepared, data)[0] == 0
    assert hook("agent-start", as_prepared, data)[0] == 2  # once


# ---------------------------------------------------------------- answers


def wrap(found: dict) -> str:
    return "Here is my answer.\n\n```json\n" + json.dumps(found, indent=1) + "\n```\n"


THESIS = {
    "claim": "c",
    "edge": "e",
    "catalyst": "k",
    "catalyst_date": "2027-06-01",
    "probability": "60%",
    "risks": "r",
    "sell_if": "s",
}
DECISIONS = {
    "fund": "careful",
    "decisions": [
        {"cik": 101, "action": "buy", "size_pct": "3%", "thesis": THESIS, "sources": [{"n": 12, "summary": "s"}]},
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
    # A draft earlier in the answer does not spoil it: only the last block is read. Other line endings are fine.
    draft = 'First I thought:\n\n```json\n{"fund": "careful", "decisions": "?"}\n```\n\nBut on reflection:\n\n'
    assert answers.parse(draft + wrap(DECISIONS), "decisions") == DECISIONS
    assert answers.parse(wrap(DECISIONS).replace("\n", "\r\n"), "decisions") == DECISIONS
    # Plain words after the block are ignored, as all words outside it are: they do not spoil the answer.
    assert (
        answers.parse(wrap(DECISIONS) + "\nWhat I left out: the full tables.\nFiles read: a, b.", "decisions")
        == DECISIONS
    )


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
        wrap(DECISIONS) + "```json\n{not json}\n```\n",
        wrap(DECISIONS) + '\nOn reflection:\n\n```json\n{"fund": "careful",',  # a second block, unfinished
        wrap(DECISIONS) + "\nAlso:\n\n```\nbuy more\n```\n",  # any block after it, not only one marked json
        "```json\n[1, 2]\n```\n",
        "```json\n" + "[" * 100_000 + "]" * 100_000 + "\n```\n",
        wrap(change(DECISIONS, "decisions/0/size_pct", 3)),
        wrap(change(DECISIONS, "decisions/0/size_pct", "3")),
        wrap(DECISIONS).replace('"3%"', "0.03"),
        wrap(DECISIONS).replace('"fund": "careful",', '"fund": "careful", "fund": "bold",'),
        wrap(change(DECISIONS, "decisions/0/thesis", ...)),
        wrap(change(DECISIONS, "decisions/0/size_pct", ...)),
        wrap(change(DECISIONS, "decisions/0/size_pct", "0%")),
        wrap(change(DECISIONS, "decisions/0/thesis/probability", "160%")),
        wrap(change(DECISIONS, "decisions/0/thesis/sell_if", "")),
        wrap(change(DECISIONS, "decisions/0/sources", [12])),
        wrap(change(DECISIONS, "decisions/1/reason", ...)),
        wrap(change(DECISIONS, "decisions/1/size_pct", "2%")),
        wrap(change(DECISIONS, "decisions/1/cik", 101)),
        wrap(change(DECISIONS, "decisions/1/cik", "102")),
        wrap(change(DECISIONS, "decisions/1/action", "short")),
        wrap(change(DECISIONS, "fund", "dice")),
        wrap(change(DECISIONS, "We buy 101 because the sell rule was met", "x")),
        wrap(change(DECISIONS, "decisions", [DECISIONS["decisions"][1] | {"cik": 200 + i} for i in range(6)])),
    ],
)
def test_an_answer_that_is_not_in_its_form_is_thrown_away(text: str) -> None:
    with pytest.raises(answers.AnswerError) as refused:
        answers.parse(text, "decisions")
    assert "sell rule was met" not in str(refused.value)  # the message says what is wrong, not what was said


def test_a_section_with_forecasts_and_resolved_ones() -> None:
    source = [{"n": 12, "summary": "The registry record."}]
    forecast = {
        "event": "The main goal of trial NCT01234567 is met",
        "event_kind": "trial result",
        "by_date": "2027-06-01",
    }
    forecast |= {"probability": "60%", "make_or_break": True, "reasoning": "Why.", "sources": source}
    section = {
        "cik": 101,
        "section": "The trial is well designed.",
        "forecasts": [forecast],
        "resolved": [
            {"forecast": 7, "result": "yes", "resolved_on": "2027-02-02", "summary": "Met.", "sources": source}
        ],
        "sources": source,
        "lacked": [],
    }
    assert answers.parse(wrap(section), "section")["forecasts"][0]["probability"] == "60%"
    bad = (
        ("forecasts/0/by_date", "June"),
        ("forecasts/0/event_kind", "price"),
        ("resolved/0/result", "maybe"),
        ("cik", "101"),
    )
    for path, value in (*bad, ("forecasts/0/sources", [12])):  # every list of sources has the one form
        with pytest.raises(answers.AnswerError):
            answers.parse(wrap(change(section, path, value)), "section")
    with pytest.raises(answers.AnswerError, match="unknown kind"):
        answers.parse(wrap(section), "poem")
