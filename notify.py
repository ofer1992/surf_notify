#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests",
#     "beautifulsoup4",
#     "matplotlib",
# ]
# ///
"""Evaluate surf forecast and send Pushover notification if waves are rideable."""

import os
import sys
from datetime import datetime, timedelta, timezone

from forecast import fetch_forecast, degree_to_compass
from chart import generate_chart

# Surfable thresholds
MIN_HEIGHT = 0.5   # meters
MIN_PERIOD = 5.0   # seconds
WIND_WARN = 15.0   # knots
MAX_DAYS = 3

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"


def find_surfable_windows(forecast: list[dict]) -> list[dict]:
    """Return timesteps within MAX_DAYS that meet surfable conditions."""
    cutoff = datetime.now(timezone.utc) + timedelta(days=MAX_DAYS)
    return [
        f for f in forecast
        if f["datetime"] <= cutoff
        and f["wave_height_m"] >= MIN_HEIGHT
        and f["wave_period_sec"] >= MIN_PERIOD
    ]


def find_best_window(windows: list[dict]) -> dict:
    """Find the best surfable window: highest Hs with lightest wind."""
    light = [w for w in windows if w["wind_speed_knots"] < WIND_WARN]
    pool = light if light else windows
    return max(pool, key=lambda w: w["wave_height_m"])


def format_message(windows: list[dict], best: dict) -> str:
    """Build the notification message text."""
    peak = max(windows, key=lambda w: w["wave_height_m"])
    peak_dt = peak["datetime"].strftime("%a %d/%m %H:%M")
    direction = degree_to_compass(peak["wave_direction"])

    lines = [
        "\U0001f3c4 Surf Alert \u2014 Tel Aviv\n",
        f"Peak: {peak['wave_height_m']:.1f}m @ {peak['wave_period_sec']:.0f}s on {peak_dt}",
        f"Direction: {direction} ({peak['wave_direction']:.0f}\u00b0)\n",
        f"Surfable windows (next {MAX_DAYS} days):",
    ]

    for w in windows:
        dt = w["datetime"].strftime("  %a %d/%m %H:%M")
        wind_flag = " \u26a0\ufe0f" if w["wind_speed_knots"] > WIND_WARN else ""
        wind_dir = degree_to_compass(w["wind_direction"])
        lines.append(
            f"{dt}  {w['wave_height_m']:.1f}m  {w['wave_period_sec']:.0f}s  "
            f"{w['wind_speed_knots']:.0f}kt {wind_dir}{wind_flag}"
        )

    best_dt = best["datetime"].strftime("%a %d/%m %H:%M")
    lines.append(
        f"\nBest window: {best_dt} \u2014 {best['wave_height_m']:.1f}m "
        f"@ {best['wave_period_sec']:.0f}s, wind {best['wind_speed_knots']:.0f}kt"
    )

    return "\n".join(lines)


def send_pushover(message: str, image_path: str | None = None) -> None:
    """Send a Pushover notification with optional image attachment."""
    import requests

    user_key = os.environ["PUSHOVER_USER_KEY"]
    api_token = os.environ["PUSHOVER_API_TOKEN"]

    data = {
        "token": api_token,
        "user": user_key,
        "title": "\U0001f3c4 Surf Forecast",
        "message": message,
        "html": "0",
    }

    files = None
    if image_path:
        files = {"attachment": ("forecast.png", open(image_path, "rb"), "image/png")}

    resp = requests.post(PUSHOVER_URL, data=data, files=files, timeout=30)
    resp.raise_for_status()
    print(f"Pushover sent: {resp.json()}")


def main():
    dry_run = "--dry-run" in sys.argv

    print("Fetching forecast...")
    forecast = fetch_forecast()
    print(f"Got {len(forecast)} timesteps")

    windows = find_surfable_windows(forecast)
    if not windows:
        print("No surfable windows found. Exiting.")
        return

    best = find_best_window(windows)
    message = format_message(windows, best)

    print("Generating chart...")
    chart_path = generate_chart(forecast, max_days=MAX_DAYS)

    if dry_run:
        print("\n--- DRY RUN ---")
        print(message)
        print(f"\nChart saved to: {chart_path}")
        return

    print("Sending notification...")
    send_pushover(message, chart_path)
    print("Done!")


if __name__ == "__main__":
    main()
