"""monitors/weather.py — Open-Meteo weather fetch."""

import requests

WMO_CODES: dict[int, str] = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Heavy freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light showers", 81: "Showers", 82: "Heavy showers",
    85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ hail", 99: "Thunderstorm w/ heavy hail",
}


def fetch(lat_lon: str) -> tuple[str, str, str]:
    """
    Returns (temp_str, humidity_str, description).
    Returns ("?", "?", "Unavailable") on any failure.
    """
    try:
        lat, lon = [p.strip() for p in lat_lon.split(",")]
        lat, lon = float(lat), float(lon)
    except Exception:
        return "?", "?", "Bad location"

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,weather_code"
        "&temperature_unit=celsius&timezone=auto"
    )
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        c = r.json()["current"]
        return (
            str(round(c["temperature_2m"])),
            str(c["relative_humidity_2m"]),
            WMO_CODES.get(c["weather_code"], "Unknown"),
        )
    except Exception as e:
        print(f"[Weather] {e}")
        return "?", "?", "Unavailable"
