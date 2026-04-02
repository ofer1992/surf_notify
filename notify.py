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

from forecast import fetch_forecast, degree_to_compass, degree_to_arrow
from chart import generate_chart

# Surfable thresholds
MIN_HEIGHT = 0.5   # meters
MIN_PERIOD = 5.0   # seconds
WIND_WARN = 15.0   # knots
MAX_DAYS = 3

NIGHT_HOURS = {21, 0, 3}  # hours to exclude from display

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


def rate_slot(w: dict) -> int:
    """Rate a surf slot 1-5 stars.

    Factors: wave height, swell period, wind speed, wind direction.
    Tel Aviv faces west (~270°), so east winds (~90°) are offshore (best).
    """
    score = 0.0

    # Wave height component (0-2 points)
    hs = w["wave_height_m"]
    if hs >= 2.0:
        score += 2.0
    elif hs >= 1.0:
        score += 1.0 + (hs - 1.0)  # 1.0-2.0
    else:
        score += hs  # 0-1.0

    # Period component (0-1.5 points)
    per = w["wave_period_sec"]
    if per >= 12:
        score += 1.5
    elif per >= 8:
        score += 0.75 + 0.75 * (per - 8) / 4  # 0.75-1.5
    elif per >= 5:
        score += 0.75 * (per - 5) / 3  # 0-0.75
    # below 5s: no points

    # Wind component (0-1.5 points)
    # Direction: 90° (E, offshore) = best, 270° (W, onshore) = worst
    # Use cosine of angle offset from ideal offshore (90°)
    import math
    wind_dir_rad = math.radians(w["wind_direction"] - 90)
    offshore_factor = math.cos(wind_dir_rad)  # +1 offshore, -1 onshore

    wind_kt = w["wind_speed_knots"]
    if wind_kt <= 5:
        # Glassy — near-perfect regardless of direction
        score += 1.3
    elif wind_kt <= 10:
        # Light wind — direction matters a bit
        base = 1.0 + 0.3 * max(offshore_factor, 0)
        score += base * (1 - (wind_kt - 5) / 20)  # slight penalty for speed
    elif wind_kt <= 15:
        # Moderate — direction matters a lot
        if offshore_factor > 0:
            score += 0.5 + 0.3 * offshore_factor
        else:
            score += max(0, 0.3 + 0.3 * offshore_factor)
    elif wind_kt <= 25:
        # Strong — only offshore saves it
        if offshore_factor > 0.5:
            score += 0.3
        # else: 0
    # above 25kt: no wind points

    # Map to 1-5 stars (score range roughly 0-5)
    stars = round(score)
    return max(1, min(5, stars))


STAR_DISPLAY = {1: "\u2581", 2: "\u2583", 3: "\u2585", 4: "\u2587", 5: "\u2588"}


def find_best_window(windows: list[dict]) -> dict:
    """Find the best surfable window by star rating, then height."""
    return max(windows, key=lambda w: (rate_slot(w), w["wave_height_m"]))


def format_message(windows: list[dict], best: dict) -> str:
    """Build the notification message text."""
    best_dt = best["datetime"].strftime("%a %d/%m %H:%M")

    lines = [
        "\U0001f3c4 Surf Alert \u2014 Tel Aviv\n",
        f"Best window: {best_dt} \u2014 {best['wave_height_m']:.1f}m "
        f"@ {best['wave_period_sec']:.0f}s, wind {best['wind_speed_knots']:.0f}kt\n",
        f"Surfable windows (next {MAX_DAYS} days):",
    ]

    daytime = [w for w in windows if w["datetime"].hour not in NIGHT_HOURS]
    for w in daytime:
        dt = w["datetime"].strftime("%a %d/%m %H:%M")
        wind_arrow = degree_to_arrow(w["wind_direction"])
        stars = rate_slot(w)
        star_str = "\u2605" * stars + "\u2606" * (5 - stars)
        best_mark = " \u2b50" if w is best else ""
        lines.append(f"{star_str} {dt}{best_mark}")
        lines.append(f"  {w['wave_height_m']:.1f}m  {w['wave_period_sec']:.0f}s  {w['wind_speed_knots']:.0f}kt {wind_arrow}")

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

    daytime_windows = [w for w in windows if w["datetime"].hour not in NIGHT_HOURS]
    best = find_best_window(daytime_windows if daytime_windows else windows)
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
