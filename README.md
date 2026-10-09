# python_ai_travel_planner

## Planner chatbot (multi-agent, Groq)

`POST /chat` with JSON `{"text": "...", "session_id": "..."}` returns `{"result": "OK", "text": "..."}`.

A manager agent (Groq) picks the specialists and extracts trip details, remembering them per `session_id`
(in memory, single process). Specialists run in parallel and the manager composes the reply from their data.

| Agent | Source | Key |
|---|---|---|
| weather | Open-Meteo | none |
| activities | OpenStreetMap Overpass + Wikipedia | none |
| flights | Travelpayouts / Aviasales | `TRAVELPAYOUTS_TOKEN` |
| hotels | RapidAPI Booking.com (DataCrawler) | `RAPIDAPI_KEY` |

Copy `.env.example` to `.env` and fill in `GROQ_API_KEY` (required) plus the optional keys.
An agent whose key is missing reports itself unavailable; the others still answer.
