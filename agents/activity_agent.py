import math

import requests

from services.geocode import geocode_city

# Public, keyless Overpass (OpenStreetMap) mirrors; the first that answers wins.
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
]
# Overpass and Wikimedia reject the default python-requests User-Agent.
HEADERS = {"User-Agent": "ai-travel-planner/1.0 (travel chatbot backend)"}
TOURISM_TAGS = "attraction|museum|viewpoint|gallery|artwork|zoo|theme_park|aquarium"
HISTORIC_TAGS = "monument|castle|memorial|ruins|archaeological_site"
WIKI_SUMMARY_URL = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"

REQUIRES = ["destination_city"]


def _distance_m(lat1, lon1, lat2, lon2) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((phi2 - phi1) / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371000 * math.asin(math.sqrt(a))


def _overpass(query: str) -> list[dict]:
    errors = []
    for url in OVERPASS_MIRRORS:
        try:
            resp = requests.post(url, data={"data": query}, headers=HEADERS, timeout=25)
            resp.raise_for_status()
            return resp.json().get("elements") or []
        except (requests.RequestException, ValueError) as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError("All Overpass mirrors failed: " + "; ".join(errors))


def _wikipedia_summary(wikipedia_tag: str | None) -> str | None:
    if not wikipedia_tag or ":" not in wikipedia_tag:
        return None
    lang, title = wikipedia_tag.split(":", 1)
    try:
        resp = requests.get(
            WIKI_SUMMARY_URL.format(lang=lang, title=title.replace(" ", "_")),
            headers=HEADERS, timeout=10,
        )
    except requests.RequestException:
        return None
    return resp.json().get("extract") if resp.ok else None


def run(trip: dict, radius_m: int = 6000, limit: int = 8) -> dict:
    """Nearby attractions from OpenStreetMap, described by Wikipedia when tagged."""
    place = geocode_city(trip["destination_city"])
    lat, lon = place["latitude"], place["longitude"]
    elements = _overpass(
        f'[out:json][timeout:20];'
        f'(node["tourism"~"{TOURISM_TAGS}"](around:{radius_m},{lat},{lon});'
        f'node["historic"~"{HISTORIC_TAGS}"](around:{radius_m},{lat},{lon}););'
        f'out body {limit * 5};'
    )

    seen, activities = set(), []
    for el in elements:
        tags = el.get("tags") or {}
        name = tags.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        activities.append({
            "name": name,
            "kind": tags.get("tourism") or tags.get("historic"),
            "distance_m": round(_distance_m(lat, lon, el["lat"], el["lon"])),
            "wikipedia_tag": tags.get("wikipedia"),
        })
    activities = sorted(activities, key=lambda a: a["distance_m"])[:limit]
    for a in activities:
        a["description"] = _wikipedia_summary(a.pop("wikipedia_tag"))
    return {"city": place["name"], "activities": activities}
