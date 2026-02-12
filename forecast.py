"""Fetch and parse ISRAMAR wave forecast data for a given location."""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone


# Tel Aviv offshore point
DEFAULT_LON = 34.70
DEFAULT_LAT = 32.08

ISRAMAR_URL = "https://isramar.ocean.org.il/isramar2009/wave_model/InfoLabel.aspx"


def _auto_modeldate() -> str:
    """Generate modeldate as today at midnight UTC in YYMMDDHHMM format."""
    return datetime.now(timezone.utc).strftime("%y%m%d") + "0000"


def fetch_forecast(
    lon: float = DEFAULT_LON,
    lat: float = DEFAULT_LAT,
    model: str = "wam",
    region: str = "fine",
    modeldate: str | None = None,
) -> list[dict]:
    """Fetch wave forecast from ISRAMAR and return list of timestep dicts.

    Each dict contains: datetime, wave_height_m, wave_direction,
    wave_period_sec, wind_speed_knots, wind_direction.
    """
    if modeldate is None:
        modeldate = _auto_modeldate()

    resp = requests.get(
        ISRAMAR_URL,
        params={"x": lon, "y": lat, "model": model, "modeldate": modeldate, "region": region},
        timeout=30,
    )
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    base_dt = datetime.strptime("20" + modeldate, "%Y%m%d%H%M").replace(tzinfo=timezone.utc)

    results = []
    for i in range(41):
        wav = soup.find(id=f"wav{i}")
        wnd = soup.find(id=f"wnd{i}")
        if not wav or not wnd:
            break

        wc = [td.text.strip() for td in wav.find_all("td")]
        nc = [td.text.strip() for td in wnd.find_all("td")]

        results.append({
            "datetime": base_dt + timedelta(hours=3 * i),
            "wave_height_m": float(wc[2]),
            "wave_direction": float(wc[5]),
            "wave_period_sec": float(wc[8]),
            "wind_speed_knots": float(nc[5]),
            "wind_direction": float(nc[8]),
        })

    return results


def degree_to_compass(deg: float) -> str:
    """Convert degrees to 16-point compass direction."""
    dirs = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
    ]
    return dirs[round(deg / 22.5) % 16]
