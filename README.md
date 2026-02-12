# Surf Notify

Daily surf forecast checker for Tel Aviv. Fetches wave model data from ISRAMAR and sends a Pushover notification when conditions are surfable.

## How it works

1. Fetches 5-day wave forecast from ISRAMAR's WAM model (3h intervals)
2. Filters for surfable windows: wave height >= 0.5m AND period >= 5s within 3 days
3. Generates a forecast chart (height, period, wind)
4. Sends a Pushover notification with the chart attached

## Local usage

```bash
# Dry run (prints to stdout, no notification sent)
uv run notify.py --dry-run

# Send notification (requires PUSHOVER_USER_KEY and PUSHOVER_API_TOKEN env vars)
PUSHOVER_USER_KEY=xxx PUSHOVER_API_TOKEN=xxx uv run notify.py
```

## GitHub Actions

Runs daily at 6am Israel time via cron. Add `PUSHOVER_USER_KEY` and `PUSHOVER_API_TOKEN` as repository secrets.
