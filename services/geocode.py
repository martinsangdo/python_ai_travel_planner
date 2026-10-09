import requests

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"


def geocode_city(city_name: str) -> dict:
    """Free, keyless Open-Meteo geocoding. Raises ValueError if the city is unknown."""
    resp = requests.get(
        GEOCODE_URL,
        params={"name": city_name, "count": 1, "language": "en", "format": "json"},
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json().get("results") or []
    if not results:
        raise ValueError(f"Could not find coordinates for city '{city_name}'.")
    top = results[0]
    return {
        "name": top["name"],
        "country": top.get("country"),
        "latitude": top["latitude"],
        "longitude": top["longitude"],
    }
