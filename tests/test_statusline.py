"""The project's status line (`.claude/statusline.py`): it prints one line and saves the usage figures."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".claude" / "statusline.py"

EVENT = {
    "session_id": "abc-123",
    "model": {"display_name": "Opus 5.5"},
    "context_window": {"used_percentage": 12.4},
    "workspace": {"current_dir": "/somewhere/bobby-hedgefund"},
    "rate_limits": {
        "five_hour": {"used_percentage": 23.5, "resets_at": 1738425600},
        "seven_day": {"used_percentage": 41.2, "resets_at": 1738857600},
    },
}


def run(data: Path, stdin: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "BOBBY_DATA_DIR": str(data)}
    return subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True, env=env)


def saved(data: Path) -> dict:
    return json.loads((data / "usage" / "rate-limits.json").read_text())


def test_the_line_shows_the_figures_and_they_are_saved(tmp_path: Path) -> None:
    done = run(tmp_path, json.dumps(EVENT))
    assert done.returncode == 0 and done.stderr == ""
    assert done.stdout == "Opus 5.5 | ctx 12% | 5h 24% · week 41% | bobby-hedgefund\n"
    found = saved(tmp_path)
    assert found["five_hour"] == {"used_percentage": 23.5, "resets_at": 1738425600}
    assert found["seven_day"]["used_percentage"] == 41.2 and found["session_id"] == "abc-123"
    assert found["saved_at"].endswith("Z") and set(found) == {"five_hour", "seven_day", "saved_at", "session_id"}
    assert (tmp_path / "usage" / "rate-limits.json").stat().st_mode & 0o077 == 0
    assert [p.name for p in (tmp_path / "usage").iterdir()] == ["rate-limits.json"]  # no temporary file left


def test_unchanged_figures_are_not_written_again_at_once(tmp_path: Path) -> None:
    run(tmp_path, json.dumps(EVENT))
    target = tmp_path / "usage" / "rate-limits.json"
    os.utime(target, (1, 1))
    first = target.read_text()
    run(tmp_path, json.dumps(EVENT))  # saved too long ago: written again
    assert target.stat().st_mtime > 1
    second = target.stat().st_mtime_ns
    run(tmp_path, json.dumps(EVENT))
    assert target.stat().st_mtime_ns == second
    changed = {**EVENT, "rate_limits": {"five_hour": {"used_percentage": 30}}}
    run(tmp_path, json.dumps(changed))
    assert saved(tmp_path)["five_hour"] == {"used_percentage": 30} and "seven_day" not in saved(tmp_path)
    assert first != target.read_text()


def test_without_figures_nothing_is_saved_and_the_line_is_still_printed(tmp_path: Path) -> None:
    event = {k: v for k, v in EVENT.items() if k != "rate_limits"}
    done = run(tmp_path, json.dumps(event))
    assert done.returncode == 0 and done.stdout == "Opus 5.5 | ctx 12% | bobby-hedgefund\n"
    assert not (tmp_path / "usage").exists()


def test_figures_out_of_range_or_of_the_wrong_kind_are_dropped(tmp_path: Path) -> None:
    event = {**EVENT, "rate_limits": {"five_hour": {"used_percentage": -1}, "seven_day": {"used_percentage": "40"}}}
    done = run(tmp_path, json.dumps(event))
    assert done.returncode == 0 and "5h" not in done.stdout and not (tmp_path / "usage").exists()
    event = {**EVENT, "rate_limits": {"five_hour": {"used_percentage": True}, "seven_day": [1]}}
    assert run(tmp_path, json.dumps(event)).returncode == 0 and not (tmp_path / "usage").exists()


def test_broken_input_or_an_unwritable_folder_still_gives_a_line(tmp_path: Path) -> None:
    for stdin in ("", "not json", "[1, 2]", json.dumps({"model": "x", "workspace": 3, "context_window": None})):
        done = run(tmp_path, stdin)
        assert done.returncode == 0 and done.stdout.startswith("Claude | ctx 0%") and done.stderr == ""
    blocked = tmp_path / "file"
    blocked.write_text("")  # the data folder is a file: saving fails
    done = run(blocked, json.dumps(EVENT))
    assert done.returncode == 0 and done.stdout.startswith("Opus 5.5 | ctx 12% | 5h 24%")


def test_the_data_folder_is_never_created_and_left_temporary_files_are_cleared(tmp_path: Path) -> None:
    missing = tmp_path / "no-data-folder"
    assert run(missing, json.dumps(EVENT)).stdout.startswith("Opus 5.5") and not missing.exists()
    (tmp_path / "usage").mkdir()
    left = tmp_path / "usage" / ".tmp-1-rate-limits.json"
    left.write_text("{")
    os.utime(left, (1, 1))
    recent = tmp_path / "usage" / ".tmp-2-rate-limits.json"
    recent.write_text("{")  # perhaps still being written by another run
    run(tmp_path, json.dumps(EVENT))
    assert not left.exists() and recent.exists() and saved(tmp_path)["seven_day"]["used_percentage"] == 41.2


def test_another_session_with_the_same_figures_does_not_write_again(tmp_path: Path) -> None:
    run(tmp_path, json.dumps(EVENT))
    target = tmp_path / "usage" / "rate-limits.json"
    first = target.stat().st_mtime_ns
    run(tmp_path, json.dumps({**EVENT, "session_id": "other"}))
    assert target.stat().st_mtime_ns == first
