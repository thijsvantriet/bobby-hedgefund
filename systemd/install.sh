#!/usr/bin/env bash
# Install the daily archive timer for the current user. Idempotent: safe to run again after a change.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project="$HOME/projects/bobby-hedgefund"
[ -d "$project/src/bobby_hedgefund" ] || { echo "$project is missing or on a branch without the archive code"; exit 1; }
install -d -m 0700 "$HOME/bobby-hedgefund-data"   # private; holds the archive (docs/decisions/0001)
(cd "$project" && uv sync --frozen --quiet)       # the timer runs with --no-sync
dest="$HOME/.config/systemd/user"
mkdir -p "$dest"
cp "$here"/bobby-archive.service "$here"/bobby-archive.timer "$here"/bobby-archive-alert.service "$dest"/
systemctl --user daemon-reload
systemctl --user enable --now bobby-archive.timer
systemctl --user list-timers bobby-archive.timer --no-pager
