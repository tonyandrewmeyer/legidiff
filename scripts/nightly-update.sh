#!/bin/bash
# Nightly update, run from cron on a machine with a residential IP.
#
# GitHub Actions can't do this yet: www.legislation.govt.nz answers a
# datacentre IP with a WAF challenge, so until legidiff reads from the API
# the update has to run from here.
#
#   15 7 * * * /home/tameyer/non-canonical/legidiff/scripts/nightly-update.sh
#
# Pushing relies on the gh credential helper in ~/.gitconfig, which works
# without a terminal.
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="$repo_dir/out/nz-acts"
log_dir="${XDG_STATE_HOME:-$HOME/.local/state}/legidiff"
mkdir -p "$log_dir"

exec >>"$log_dir/update.log" 2>&1
echo "=== $(date --iso-8601=seconds) ==="

# One run at a time: a sweep can take hours, and two runs would fight over
# the same repository.
exec 9>"$log_dir/update.lock"
if ! flock -n 9; then
    echo "another run holds the lock, skipping"
    exit 0
fi

cd "$repo_dir"
/usr/bin/python3 -m legidiff update --repo "$target"

if [ -n "$(git -C "$target" log --oneline '@{u}..HEAD')" ]; then
    git -C "$target" log --oneline '@{u}..HEAD' | head -50
    git -C "$target" push origin HEAD:main
else
    echo "nothing new to push"
fi
