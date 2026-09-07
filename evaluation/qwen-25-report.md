# Qwen3.5 9B: 25 chat scenarios

Result: 17 pass, 4 partial, 4 fail. This is a hand-reviewed scenario set, not a general model-accuracy benchmark.

Method: requests sent to the running /api/chat endpoint; route intents then sent to /api/map/journey exactly as the frontend does. Follow-ups use context returned by earlier test turns. No browser clicking or visual QA. OneMap connected during this run. Route mode and geometry checked against the returned OneMap payload; operator schedules/travel times not independently verified. Timetable, stop-service and service-itinerary facts checked against the January 2026 SQLite snapshot. UI response omissions assessed from app/page.tsx.

| # | Scenario / question | Result | Finding |
|---|---|---|---|
| 1 | From Woodlands Int to Hougang Int | Pass | Route/data returned as expected, or unsupported data explicitly declined. |
| 2 | What about Pasir Ris? | Pass | Route/data returned as expected, or unsupported data explicitly declined. |
| 3 | Opposite direction | Pass | Route/data returned as expected, or unsupported data explicitly declined. |
| 4 | I am at Serangoon and want to reach Bartley. Which bus can I take? | Pass | Route/data returned as expected, or unsupported data explicitly declined. |
| 5 | From 46009 to 64009 | Pass | Route/data returned as expected, or unsupported data explicitly declined. |
| 6 | From Wdlands Int to Hougang Ctrl Int | Pass | Route/data returned as expected, or unsupported data explicitly declined. |
| 7 | Which buses serve stop 66009? | Pass | Route/data returned as expected, or unsupported data explicitly declined. |
| 8 | List the stops for bus 161 | Pass | Route/data returned as expected, or unsupported data explicitly declined. |
| 9 | Last bus 168 at Woodlands Int | Pass | Route/data returned as expected, or unsupported data explicitly declined. |
| 10 | What about Sunday? | Pass | Route/data returned as expected, or unsupported data explicitly declined. |
| 11 | First bus 161 at Woodlands Int on Saturday | Pass | Route/data returned as expected, or unsupported data explicitly declined. |
| 12 | last bus 168 | Pass | Route/data returned as expected, or unsupported data explicitly declined. |
| 13 | Woodlands Int | Pass | Route/data returned as expected, or unsupported data explicitly declined. |
| 14 | Which buses serve stop 99999? | Pass | Route/data returned as expected, or unsupported data explicitly declined. |
| 15 | Last bus 999 at Woodlands Int | Pass | Route/data returned as expected, or unsupported data explicitly declined. |
| 16 | From Woodlands to Atlantis | Partial | OneMap resolves Atlantis to a named place automatically; ambiguous matches need confirmation. |
| 17 | From Woodlands Int to Woodlands Int | Partial | No journey returned correctly, but the UI replaces the helpful same-location message with a generic failure. |
| 18 | When will the next bus 168 arrive? | Pass | Route/data returned as expected, or unsupported data explicitly declined. |
| 19 | How much is the fare from Woodlands to Hougang? | Pass | Route/data returned as expected, or unsupported data explicitly declined. |
| 20 | Where is the nearest bus stop to me? | Partial | Generic unsupported response; does not offer the existing location control. |
| 21 | Direct buses only from Woodlands to Pasir Ris | Fail | Explicit direct-only request returns multi-bus journeys. |
| 22 | Less walking please | Fail | Walking preference is discarded; repeats the original search. |
| 23 | From Woodlands to Hougang tomorrow at 8am | Fail | Tomorrow at 8am is treated as part of the destination, and lookup fails. |
| 24 | How long does it take from Woodlands to Hougang? | Partial | OneMap supplies 69 minutes and the map can display it, but the chat response omits duration. |
| 25 | Where do I change for the second route? | Fail | Second-route question is misclassified as a stop lookup; prior itineraries are not retained in conversation context. |

Median combined API latency: 1.00 seconds. Maximum: 2.39 seconds. Includes rule-only replies, excludes browser rendering.

The direct-only, walking and date/time constraints are not represented in the current model schema or forwarded to routing. The deterministic parser overrides model output for recognized patterns, including the future-departure example. Previous route options are also absent from the context sent to Qwen. A model upgrade alone does not resolve these gaps.