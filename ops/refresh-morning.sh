#!/bin/bash
# Build today's morning brief and publish it to the site repository.
# Runs from launchd (com.wendy.park-morning) at 09:00 and 09:40 Beijing time.
# Kill switch: MORNING_DISABLED=1, or a file at ~/.park-morning.off
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
REPO="/Users/wendy/work/park-morning"
SITE="${MORNING_SITE_REPO:-/Users/wendy/work/park-ai-intel}"
OUT="public/daily"
LOG="$REPO/ops/refresh-morning.log"
PY=/usr/local/bin/python3

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z') · morning refresh ==="
  if [ "${MORNING_DISABLED:-0}" = "1" ] || [ -f "$HOME/.park-morning.off" ]; then
    echo "· disabled — skip"; echo "=== done ==="; exit 0
  fi

  cd "$REPO" || exit 1
  "$PY" build-morning.py --send-feishu --alert || { echo "✗ build failed"; exit 1; }

  cd "$SITE" || exit 1
  # Bring the publishing branch up to date first, so the push is a fast-forward.
  git pull --rebase --autostash -q origin main || { echo "✗ rebase onto origin/main failed"; exit 1; }
  if [ -z "$(git status --porcelain -- "$OUT")" ]; then
    echo "· no content change — nothing to publish"
  else
    git add "$OUT" \
      && git commit -q -m "chore: morning brief $(date '+%Y-%m-%d')" -- "$OUT" \
      && git push -q origin HEAD:main \
      && echo "✓ published: $(git show --stat --format= HEAD | tail -n +1 | head -3 | tr -s ' ' | tr '\n' ';')" \
      || echo "✗ commit/push failed"
  fi
  echo "=== done ==="
} >> "$LOG" 2>&1
