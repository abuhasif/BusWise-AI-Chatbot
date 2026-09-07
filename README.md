# Buswise

A local conversational bus-route assistant using React, Python, SQLite and Qwen3.5 9B through Ollama. Qwen interprets questions into a small validated query structure. Python supplies answers from database records; the model does not generate route facts or SQL.

## Run locally

Run `.\start-local.ps1` in PowerShell from this project. Open http://127.0.0.1:3000. Use `.\stop-local.ps1` to stop only services launched by that script. The initial build uses the installed Codex Python runtime and portable Ollama already downloaded in the parent workspace; the script accepts alternate paths for portability.

## Clone and run on another computer

Install Node 22.13+ and Python 3.11+, then run `npm ci` and `python -m pip install -r backend/requirements.txt`. Install Ollama and pull `qwen3.5:9b`. The public January 2026 route snapshot is included as `data/bus.db`, so importing a workbook is optional. Run `ollama serve`, `python backend/server.py`, and `npm run dev` in separate terminals. Without Ollama, supported patterns use the labelled database fallback.

## Try these

Select **Use my location** to request a one-time browser location fix. The app displays up to five stops with recorded services within 2 km, sorted by Haversine straight-line distance. Each stop has **Show buses** and **Use as starting stop** actions. The latter fills the route question so you only need to add your destination. Location accuracy, permission denial, timeout and no nearby results have explicit UI states.

Coordinates are sent only to the local `/api/nearby` backend and are not stored in SQLite, written to request logs, or passed to Qwen. There is no background location tracking. The browser/OS location provider may use its own location services to obtain the fix. Distances are not walking directions; confirm stop direction and pedestrian access. The rest of the app works when location permission is declined.

If location times out, the app retries once with a longer, high-accuracy request. Permission denial does not trigger a retry. **Search by station or road** works without geolocation and opens automatically after a failed location request. It returns up to 10 named stops with service lists, not estimated distances. This also works when an embedded browser cannot supply device location.

- How can I go from Serangoon to Bartley?
- What about Aljunied? (after a route question)
- Opposite direction (after a route question)
- Which buses serve stop 66009?
- Last bus for service 100 at stop 66009 on Sunday?
- What about Saturday? (after an operating-times question)
- List stops for service 158

## Dataset and limitations

Source: Free Bus Generator caa 05-Jan-2026.xlsx. 5,194 stops, 421 services and 23,540 route-stop records. The importer preserves five-digit stop codes and stores the source hash and limitations in SQLite metadata. Original files are not changed, and the notebook or its credential is not copied or executed.

The source filters most services ending A/B/C/T and modifies loop directions. Seven duplicate sequence keys were found in service 382 direction 2, which is excluded from direct-route queries. Station matching uses supplied boarding/alighting mappings, not verified walking connections. The app searches direct buses only, orders results by stop count, and does not claim fastest routes. Service-stop lists display up to 80 records; direct-route results display up to 12 records. First/last times are dated schedules, not live predictions. No current arrivals, disruptions, fares or free-boarding activation is available.

No model training is performed. Conversations are held in browser memory, with compact structured context submitted on follow-ups. No API key or external model provider is used. This repository includes a public route-data snapshot; no OneMap credentials, model files or source workbooks are included.

## Validation

Run `python -m unittest discover -s backend -p "test_*.py"` for routing and context tests. Run `npm run build` and `npm run lint` for the frontend. Live-model evaluation cases and measured results are saved separately under `evaluation/`. This is a prototype, not an official journey planner.


## Interactive bus map and OneMap

The Leaflet map uses OneMap tiles (no token required). Click a map point or a bus-stop dot to select your start/destination. Named stops work too. Chat route queries also update the map.

For OneMap journey planning, register at https://www.onemap.gov.sg/apidocs/register and obtain an access token following https://www.onemap.gov.sg/apidocs/authentication. Set it as the `ONEMAP_TOKEN` environment variable, or create the untracked file `data/onemap-token.txt`. Do not put it in frontend code or commit it. The file is read on each request, so no restart is required. OneMap tokens expire after three days; replace an expired token. No credentials are sent to Qwen. Start/end coordinates are sent to OneMap when routing is connected.

## Repository contents

This is a single-repository local application:

- `app/` — React interface and map
- `backend/` — route search, OneMap adapter and SQLite API
- `data/bus.db` — public January 2026 bus-route snapshot
- `evaluation/` and `tests/` — conversational and interaction checks

The repository intentionally excludes the OneMap token, Ollama/Qwen model downloads, logs and locally generated process files. GitHub stores the source; run the local setup above to start the application.

Routing requests use Singapore local time, bus mode, up to three itineraries and a 1,000 m walking limit. Returned routes are independently restricted to BUS/WALK legs and must contain at least one bus. Unknown modes, rail and ferries are excluded. Named locations outside the local data use OneMap search when connected; the selected match is displayed.

Without a valid token or during an upstream failure, the map explicitly uses the January 2026 direct-bus database. Map points use the nearest recorded stop within 2 km and show its straight-line distance. Dashed fallback lines join ordered stops and do not represent actual road geometry or walking paths. Map tiles still require internet. Chat facts remain sourced from the original database.
