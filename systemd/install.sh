#!/usr/bin/env bash
# Install the daily archive timer and the morning prices timer for the current user. Idempotent: safe to run again after a change.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project="$HOME/projects/bobby-hedgefund"
[ -d "$project/src/bobby_hedgefund" ] || { echo "$project is missing or on a branch without the archive code"; exit 1; }
install -d -m 0700 "$HOME/bobby-hedgefund-data"   # private; holds the archive (docs/decisions/0001)
# Refuse to install work in progress: the nightly job must run reviewed, committed code.
if [ -n "$(git -C "$project" status --porcelain -- src pyproject.toml uv.lock)" ]; then
  echo "uncommitted changes in src/, pyproject.toml or uv.lock: commit or undo them first"; exit 1
fi
(cd "$project" && uv sync --frozen --quiet && uv run --no-sync pytest -q)   # never install code whose tests fail
# A snapshot of the program in its own environment (~/.local/share/uv/tools); the command lands in ~/.local/bin.
uv tool install --quiet --force --reinstall "$project"
echo "installed bobby-archive, bobby-prices, bobby-trials and bobby-universe from commit $(git -C "$project" rev-parse --short HEAD) ($(git -C "$project" branch --show-current))"
dest="$HOME/.config/systemd/user"
mkdir -p "$dest"
cp "$here"/bobby-archive.service "$here"/bobby-archive.timer "$here"/bobby-archive-alert.service "$dest"/
cp "$here"/bobby-prices.service "$here"/bobby-prices.timer "$here"/bobby-prices-alert.service "$dest"/
cp "$here"/bobby-trials.service "$here"/bobby-trials.timer "$here"/bobby-trials-alert.service "$dest"/
systemctl --user daemon-reload
systemctl --user enable --now bobby-archive.timer bobby-prices.timer bobby-trials.timer
systemctl --user list-timers bobby-archive.timer bobby-prices.timer bobby-trials.timer --no-pager
