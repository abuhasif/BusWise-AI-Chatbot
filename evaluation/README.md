# Initial evaluation

Measured on 5 September 2026 with local gemma3:4b and the imported January 2026 workbook.

- 15/15 automated database/routing/context checks passed.
- 12/12 end-to-end question cases passed (including two free-form paraphrases, route and timetable follow-ups, unknown inputs, and unsupported live requests).
- Frontend build and lint passed after removing unused generated UI components.

Run `python backend/evaluate.py` to reproduce the question suite. It writes `evaluation/live-results.json`, containing questions, timing, returned context and database records. Checks use explicit expected intents and result fragments rather than model self-grading. This is an initial smoke evaluation, not a statistically representative accuracy benchmark. Broaden it with independent real-user wording and a held-out set before making accuracy claims.

The optional WebMCP tool is feature-detected and routes through the same chat action. Its browser registration has not been verified in a supporting browser. Browser UI interaction testing was not requested; the frontend and HTTP integration were checked without claiming a visual browser audit.
