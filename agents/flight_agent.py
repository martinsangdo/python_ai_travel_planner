import os
from datetime import date, timedelta

import requests

AUTOCOMPLETE_URL = "https://autocomplete.travelpayouts.com/places2"
PRICES_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"

REQUIRES = ["origin_city", "destination_city", "start_date"]


def _resolve_iata(name: str) -> str:
    resp = requests.get(
        AUTOCOMPLETE_URL,
        params={"term": name, "locale": "en", "types[]": ["city", "airport"]},
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json() or []
    if not results:
        raise ValueError(f"Could not resolve an airport/city code for '{name}'.")
    # Prefer an exact name match; otherwise trust the API's relevance order
    # (its `weight` is global popularity and can pick an unrelated busy place).
    exact = next((r for r in results if r.get("name", "").lower() == name.strip().lower()), None)
    return (exact or results[0])["code"]


def _prices(origin: str, destination: str, when: str, limit: int) -> list[dict]:
    """`when` is YYYY-MM-DD or YYYY-MM. Aviasales data is a cache of what users
    found in the last 48h, not a live booking search."""
    token = os.environ.get("TRAVELPAYOUTS_TOKEN")
    if not token:
        raise RuntimeError("TRAVELPAYOUTS_TOKEN is not set (free token at https://www.travelpayouts.com).")
    resp = requests.get(
        PRICES_URL,
        params={
            "origin": origin, "destination": destination, "departure_at": when,
            "currency": "usd", "sorting": "price", "direct": "false",
            "limit": limit, "page": 1, "one_way": "true", "token": token,
        },
        timeout=20,
    )
    if not resp.ok:
        raise RuntimeError(f"Travelpayouts error {resp.status_code}: {resp.text}")
    payload = resp.json()
    if not payload.get("success", True):
        raise RuntimeError(f"Travelpayouts error: {payload.get('error')}")
    offers = []
    for o in payload.get("data") or []:
        if o.get("price") is None:
            continue
        offers.append({
            "price_usd": float(o["price"]),
            "airline": o.get("airline"),
            "flight_number": o.get("flight_number"),
            "departure_at": o.get("departure_at"),
            "transfers": o.get("transfers"),
            "link": f"https://www.aviasales.com{o['link']}" if o.get("link") else None,
        })
    return offers


def _leg(origin: str, destination: str, day: str, limit: int) -> dict:
    """Exact day first; the cache is sparse, so fall back to the whole month and say so."""
    offers = _prices(origin, destination, day, limit)
    if offers:
        return {"exact_date": True, "offers": offers}
    return {"exact_date": False, "offers": _prices(origin, destination, day[:7], limit * 3)[:limit]}


def run(trip: dict, limit: int = 5) -> dict:
    """One-way price lookups per leg (combined round-trip queries come back nearly empty)."""
    origin = _resolve_iata(trip["origin_city"])
    destination = _resolve_iata(trip["destination_city"])
    result = {
        "origin": origin,
        "destination": destination,
        "prices_are_per_traveler": True,
        "outbound": _leg(origin, destination, trip["start_date"], limit),
    }
    if trip.get("duration_days"):
        return_date = date.fromisoformat(trip["start_date"]) + timedelta(days=int(trip["duration_days"]))
        result["return_date"] = return_date.isoformat()
        result["inbound"] = _leg(destination, origin, return_date.isoformat(), limit)
    return result
