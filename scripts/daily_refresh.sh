#!/bin/bash
# Daily refresh script — pulls fresh FactSet+yfinance data, commits the
# updated SQLite DB, pushes to GitHub. Streamlit Cloud auto-redeploys.
#
# Run via launchd (see scripts/com.stephenjacobs.healthcare-multiples.plist).
# Logs to data/refresh.log.

set -euo pipefail

cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"

# shellcheck disable=SC1091
source .venv/bin/activate

LOG="$PROJECT_ROOT/data/refresh.log"
mkdir -p "$(dirname "$LOG")"
TS() { date '+%Y-%m-%d %H:%M:%S'; }

{
    echo "================================================================="
    echo "[$(TS)] Daily refresh starting"
    echo "================================================================="

    # Bail early if not on main branch — avoid clobbering work in progress.
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    if [ "$BRANCH" != "main" ]; then
        echo "[$(TS)] Skipping refresh: on branch '$BRANCH' (expected main)"
        exit 0
    fi

    # Pull latest before refreshing so we don't fight upstream commits.
    git pull --rebase --autostash origin main

    # Run the fetcher. Exits non-zero on hard errors (network, auth).
    python -m fetcher.run_fetch

    # Did the DB actually change?
    if git diff --quiet -- data/healthcare_multiples.db; then
        echo "[$(TS)] No DB changes — exiting clean."
        exit 0
    fi

    # Commit + push.
    git add data/healthcare_multiples.db
    git -c user.email="stephenwjacobs@gmail.com" \
        -c user.name="Stephen Jacobs (auto-refresh)" \
        commit -m "Daily refresh — $(date '+%Y-%m-%d')"
    git push origin main

    echo "[$(TS)] Refresh complete + pushed."
} >> "$LOG" 2>&1
