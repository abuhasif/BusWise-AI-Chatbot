# Buswise

Buswise is a local conversational assistant for Singapore bus journeys. It combines Qwen3.5 9B for query understanding, OneMap for bus-only route planning and a bundled January 2026 SQLite snapshot for stop and timetable lookups.

## What it does

- Plans bus-only journeys with walking access and transfers through OneMap
- Answers direct-route, stop-service and first/last-bus questions from the local snapshot
- Keeps route context for follow-ups such as “what about Sunday?” and “where do I change?”
- Shows routes, stops and location-selected start points on an interactive map

## Run locally

### Requirements

- Node.js 22.13+
- Python 3.11+
- [Ollama](https://ollama.com/)

### Setup

```powershell
git clone https://github.com/abuhasif/BusWise-AI-Chatbot.git
cd BusWise-AI-Chatbot
npm ci
python -m pip install -r backend/requirements.txt
ollama pull qwen3.5:9b
```

Optional: enable live OneMap route planning by setting `ONEMAP_TOKEN` in your environment, or by creating `data/onemap-token.txt`. Never commit the token.

```powershell
.\start-local.ps1
```

Open `http://127.0.0.1:3000`. Stop only services started by Buswise with:

```powershell
.\stop-local.ps1
```

The launcher uses the bundled runtime when it exists. On a fresh clone, it uses your installed `python` and `ollama` commands.

## Repository layout

```text
app/              React interface and interactive map
backend/          Python API, route logic and SQLite importer
data/bus.db       Public January 2026 route snapshot
docs/evaluation/  Conversation test suites and reports
tests/            Frontend interaction tests
```

The repository excludes OneMap credentials, downloaded models, logs and local process state.

## Data and limits

`data/bus.db` contains 5,194 stops, 421 services and 23,540 route-stop records from a January 2026 snapshot. First/last-bus times are scheduled values, not live arrivals. Current arrivals, disruption notices, fares and free-boarding status are unavailable.

OneMap results are limited to bus and walking legs. If OneMap is unavailable, Buswise labels its database fallback clearly; those dashed map lines connect recorded stops and are not road directions.

## Checks

```powershell
python -m unittest discover -s backend -p "test_*.py"
node --test tests/*.test.mjs
npm run lint
npm run build
```

See [`docs/evaluation/`](docs/evaluation/) for the conversational test cases and results.
