import json
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Lock

from agents import activity_agent, flight_agent, hotel_agent, weather_agent
from services import groq_client

SPECIALISTS = {
    "weather": weather_agent,
    "flights": flight_agent,
    "hotels": hotel_agent,
    "activities": activity_agent,
}
TRIP_FIELDS = ["origin_city", "destination_city", "start_date", "duration_days", "travelers"]

MAX_SESSIONS = 500
MAX_HISTORY = 10  # messages kept per session

_sessions: OrderedDict[str, dict] = OrderedDict()
_lock = Lock()

EXTRACTION_PROMPT = """You are the manager agent of a travel-planning chatbot.
Today's date is {today} (YYYY-MM-DD). The user may write in any language.

Decide which specialist agents are needed to answer the latest user message and
extract the trip details it mentions. Resolve relative dates ("next week",
"tomorrow", ...) into absolute YYYY-MM-DD.

Specialists:
- "weather": weather forecast for the destination
- "flights": flight tickets/prices between two cities
- "hotels": hotel offers at the destination
- "activities": attractions and things to do at the destination

Return ONLY a JSON object:
{{
  "agents": [subset of "weather", "flights", "hotels", "activities"; [] for chit-chat
             or general questions that need no live data],
  "trip": {{
    "origin_city": string or null,
    "destination_city": string or null,
    "start_date": "YYYY-MM-DD" or null,
    "duration_days": integer or null,
    "travelers": integer or null
  }}
}}

Rules:
- Only fill a "trip" field if the user message or the conversation says it. Never guess; use null.
- City names must be in English.
- If the user asks for a full trip plan, include all four agents.

Trip details known from earlier turns: {known}
Conversation so far: {history}
Latest user message: "{message}"
"""

COMPOSE_PROMPT = """You are a friendly travel-planning assistant. Reply to the user's
latest message in the language they used, concisely, in plain text (no markdown tables).

Rules:
- Use ONLY the data in "Agent results". Never invent prices, dates, flights, hotels or weather.
- Flight prices come from a cache of recent searches: mention when "exact_date" is false
  that the prices are for the same month, not the requested day.
- Weather codes are WMO codes; describe them in words. If "covers_trip_dates" is false,
  say the forecast is for the next days only because the trip is outside the forecast range.
- If an agent failed (see "Agent errors"), say briefly that this part is unavailable right now.
- If "Missing information" is not empty, ask the user for those details at the end.

Today's date: {today}
Conversation so far: {history}
Latest user message: "{message}"
Trip details: {trip}
Agent results: {results}
Agent errors: {errors}
Missing information (agent -> fields): {missing}
"""


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _get_session(session_id: str) -> dict:
    with _lock:
        session = _sessions.pop(session_id, None) or {"trip": {}, "history": []}
        _sessions[session_id] = session  # most recently used goes last
        while len(_sessions) > MAX_SESSIONS:
            _sessions.popitem(last=False)
        return session


def _extract(message: str, session: dict) -> dict:
    prompt = EXTRACTION_PROMPT.format(
        today=datetime.now().strftime("%Y-%m-%d"),
        known=_dump(session["trip"]),
        history=_dump(session["history"]),
        message=message,
    )
    result = groq_client.generate_json(prompt)
    agents = [a for a in result.get("agents") or [] if a in SPECIALISTS]
    new_trip = {k: v for k, v in (result.get("trip") or {}).items()
                if k in TRIP_FIELDS and v not in (None, "")}
    return {"agents": agents, "trip": new_trip}


def chat(session_id: str, message: str) -> str:
    """One chatbot turn: extract intent -> run specialists in parallel -> compose reply."""
    session = _get_session(session_id)
    plan = _extract(message, session)
    session["trip"].update(plan["trip"])
    trip = session["trip"]

    runnable, missing = [], {}
    for name in plan["agents"]:
        lacking = [f for f in SPECIALISTS[name].REQUIRES if trip.get(f) in (None, "")]
        if lacking:
            missing[name] = lacking
        else:
            runnable.append(name)

    results, errors = {}, {}

    def run_agent(name: str):
        try:
            return name, SPECIALISTS[name].run(dict(trip)), None
        except Exception as exc:
            return name, None, str(exc)

    with ThreadPoolExecutor(max_workers=len(SPECIALISTS)) as pool:
        for name, data, error in pool.map(run_agent, runnable):
            if error:
                errors[name] = error
            else:
                results[name] = data

    reply = groq_client.generate_text(COMPOSE_PROMPT.format(
        today=datetime.now().strftime("%Y-%m-%d"),
        history=_dump(session["history"]),
        message=message,
        trip=_dump(trip),
        results=_dump(results),
        errors=_dump(errors),
        missing=_dump(missing),
    ))

    session["history"] += [{"role": "user", "text": message}, {"role": "assistant", "text": reply}]
    del session["history"][:-MAX_HISTORY]
    return reply
