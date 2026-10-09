from datetime import date, timedelta

import requests

from services.geocode import geocode_city

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_DAYS = 16  # Open-Meteo's forecast horizon, today included

REQUIRES = ["destination_city"]


def run(trip: dict) -> dict:
    """Daily forecast from the free, keyless Open-Meteo API. Covers the trip
    dates when they fall inside the forecast horizon, otherwise the next 7 days."""
    place = geocode_city(trip["destination_city"])
    today = date.today()
    last_day = today + timedelta(days=FORECAST_DAYS - 1)

    start, end = today, today + timedelta(days=6)
    covers_trip = False
    if trip.get("start_date") and trip.get("duration_days"):
        trip_start = date.fromisoformat(trip["start_date"])
        trip_end = trip_start + timedelta(days=int(trip["duration_days"]) - 1)
        if today <= trip_start <= last_day:
            start, end, covers_trip = trip_start, min(trip_end, last_day), True

    resp = requests.get(
        FORECAST_URL,
        params={
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
            "timezone": "auto",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        timeout=15,
    )
    resp.raise_for_status()
    daily = resp.json()["daily"]

    days = [
        {
            "date": daily["time"][i],
            "temp_max_c": daily["temperature_2m_max"][i],
            "temp_min_c": daily["temperature_2m_min"][i],
            "rain_probability_pct": daily["precipitation_probability_max"][i],
            "wmo_weather_code": daily["weather_code"][i],
        }
        for i in range(len(daily["time"]))
    ]
    return {
        "city": place["name"],
        "country": place["country"],
        "covers_trip_dates": covers_trip,
        "forecast_horizon_ends": last_day.isoformat(),
        "days": days,
    }
