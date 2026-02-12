"""Generate a forecast chart with wave height, period, and wind panels."""

import tempfile
from datetime import datetime, timedelta, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


# Surfable thresholds
MIN_HEIGHT = 0.5  # meters
MIN_PERIOD = 5.0  # seconds
WIND_WARN = 15.0  # knots


def generate_chart(forecast: list[dict], max_days: int = 3) -> str:
    """Generate a 3-panel forecast chart. Returns path to PNG file."""
    cutoff = datetime.now(timezone.utc) + timedelta(days=max_days)
    data = [f for f in forecast if f["datetime"] <= cutoff]
    if not data:
        data = forecast

    times = [f["datetime"] for f in data]
    heights = [f["wave_height_m"] for f in data]
    periods = [f["wave_period_sec"] for f in data]
    winds = [f["wind_speed_knots"] for f in data]

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    fig.suptitle("Tel Aviv Surf Forecast", fontsize=14, fontweight="bold")

    # Find surfable windows for shading
    for ax in (ax1, ax2, ax3):
        for f in data:
            if f["wave_height_m"] >= MIN_HEIGHT and f["wave_period_sec"] >= MIN_PERIOD:
                t = f["datetime"]
                ax.axvspan(
                    t - timedelta(hours=1.5), t + timedelta(hours=1.5),
                    alpha=0.15, color="green", linewidth=0,
                )

    # Panel 1: Wave height
    ax1.plot(times, heights, "b-o", markersize=3, linewidth=1.5)
    ax1.axhline(MIN_HEIGHT, color="green", linestyle="--", alpha=0.5, linewidth=0.8)
    ax1.set_ylabel("Wave Height (m)")
    ax1.grid(True, alpha=0.3)

    # Panel 2: Wave period
    ax2.plot(times, periods, "purple", marker="o", markersize=3, linewidth=1.5)
    ax2.axhline(MIN_PERIOD, color="green", linestyle="--", alpha=0.5, linewidth=0.8)
    ax2.set_ylabel("Period (s)")
    ax2.grid(True, alpha=0.3)

    # Panel 3: Wind speed
    ax3.plot(times, winds, "r-o", markersize=3, linewidth=1.5)
    ax3.axhline(WIND_WARN, color="orange", linestyle="--", alpha=0.5, linewidth=0.8)
    ax3.set_ylabel("Wind (knots)")
    ax3.grid(True, alpha=0.3)

    # Annotate best window (highest Hs with wind < WIND_WARN, or just highest Hs)
    surfable = [f for f in data if f["wave_height_m"] >= MIN_HEIGHT and f["wave_period_sec"] >= MIN_PERIOD]
    if surfable:
        light_wind = [f for f in surfable if f["wind_speed_knots"] < WIND_WARN]
        pool = light_wind if light_wind else surfable
        best = max(pool, key=lambda f: f["wave_height_m"])
        ax1.annotate(
            f"Best: {best['wave_height_m']:.1f}m",
            xy=(best["datetime"], best["wave_height_m"]),
            xytext=(0, 15), textcoords="offset points",
            fontsize=8, fontweight="bold", color="darkgreen",
            arrowprops=dict(arrowstyle="->", color="darkgreen", lw=1),
            ha="center",
        )

    # Format x-axis
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%a %d/%m\n%H:%M"))
    ax3.xaxis.set_major_locator(mdates.HourLocator(interval=12))
    fig.autofmt_xdate(rotation=0, ha="center")

    plt.tight_layout()

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fig.savefig(tmp.name, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return tmp.name
