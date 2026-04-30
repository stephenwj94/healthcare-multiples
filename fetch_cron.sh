#!/bin/bash
# Daily data fetch script - add to crontab for scheduled refresh.
# Example crontab entry (5:30 PM ET weekdays):
#   30 17 * * 1-5 /Users/jamesmaycher/Tech\ Multiples/fetch_cron.sh

cd "/Users/jamesmaycher/Tech Multiples"

# Run the data fetch
python3 -m fetcher.run_fetch >> data/fetch.log 2>&1

# Push updated DB to GitHub so Streamlit Cloud picks up fresh data
git add data/healthcare_multiples.db >> data/fetch.log 2>&1
git diff --cached --quiet || git commit -m "Daily data refresh $(date '+%Y-%m-%d')" >> data/fetch.log 2>&1
git push origin main >> data/fetch.log 2>&1
