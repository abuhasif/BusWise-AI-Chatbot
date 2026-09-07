# Common bus question evaluation

18 representative queries, not measured search-popularity rankings. Tested through the running chat API and its subsequent map journey endpoint; not browser click testing. Facts compared against the January 2026 SQLite snapshot, not current operator timetables.

15 acceptable; 1 failure and 2 partial responses. All returned route legs and same-stop transfers matched the database. Returned timetable values and the stop-service listing were independently checked.

| Case | Assessment |
|---|---|
| Direct route | PASS against January 2026 snapshot / expected limitation |
| Transfer route | PASS against January 2026 snapshot / expected limitation |
| Natural wording | PASS against January 2026 snapshot / expected limitation |
| Stop services | PASS against January 2026 snapshot / expected limitation |
| Last bus | PASS against January 2026 snapshot / expected limitation |
| Missing boarding stop | PASS against January 2026 snapshot / expected limitation |
| Stop clarification | PASS against January 2026 snapshot / expected limitation |
| Day follow-up | PASS against January 2026 snapshot / expected limitation |
| Destination follow-up | PASS against January 2026 snapshot / expected limitation |
| Reverse journey | PASS against January 2026 snapshot / expected limitation |
| First bus | PASS against January 2026 snapshot / expected limitation |
| Live arrivals | PASS against January 2026 snapshot / expected limitation |
| Nearest stop | PARTIAL: generic unsupported response instead of directing user to location controls. |
| Unknown place | PASS against January 2026 snapshot / expected limitation |
| Unknown stop | PASS against January 2026 snapshot / expected limitation |
| Route time | PARTIAL: provides routes but does not explicitly answer that duration is unavailable. |
| Direct-only request | FAIL: returns transfers despite direct-only constraint. |
| Fare | PASS against January 2026 snapshot / expected limitation |