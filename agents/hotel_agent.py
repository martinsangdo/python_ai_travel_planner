import os
from datetime import date, timedelta

import requests

HOST = "booking-com15.p.rapidapi.com"
BASE_URL = f"https://{HOST}/api/v1/hotels"

REQUIRES = ["destination_city", "start_date", "duration_days"]


def _get(path: str, params: dict) -> dict:
    api_key = os.environ.get("RAPIDAPI_KEY")
    if not api_key:
        raise RuntimeError(
            "RAPIDAPI_KEY is not set (free tier of https://rapidapi.com/DataCrawler/api/booking-com15)."
        )
    resp = requests.get(
        f"{BASE_URL}/{path}",
        headers={"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": HOST},
        params=params,
        timeout=20,
    )
    if not resp.ok:
        raise RuntimeError(f"RapidAPI Booking.com error {resp.status_code}: {resp.text}")
    return resp.json() or {}


def run(trip: dict, max_results: int = 5) -> dict:
    check_in = date.fromisoformat(trip["start_date"])
    check_out = check_in + timedelta(days=int(trip["duration_days"]))

    destinations = _get("searchDestination", {"query": trip["destination_city"]}).get("data") or []
    if not destinations:
        raise ValueError(f"Could not find a hotel destination for '{trip['destination_city']}'.")
    dest = destinations[0]

    hotels = _get("searchHotels", {
        "dest_id": dest["dest_id"],
        "search_type": dest.get("search_type", "CITY"),
        "arrival_date": check_in.isoformat(),
        "departure_date": check_out.isoformat(),
        "adults": int(trip.get("travelers") or 1),
        "room_qty": 1,
        "currency_code": "USD",
        "languagecode": "en-us",
    }).get("data", {}).get("hotels") or []

    offers = []
    for entry in hotels:
        prop = entry.get("property") or {}
        price = (prop.get("priceBreakdown") or {}).get("grossPrice") or {}
        if not prop.get("name") or price.get("value") is None:
            continue
        offers.append({
            "hotel_name": prop["name"],
            "total_price": float(price["value"]),
            "currency": price.get("currency", "USD"),
            "review_score": prop.get("reviewScore"),
        })
        if len(offers) == max_results:
            break
    return {
        "city": dest.get("name", trip["destination_city"]),
        "check_in": check_in.isoformat(),
        "check_out": check_out.isoformat(),
        "price_is_total_for_stay_one_room": True,
        "offers": offers,
    }
