# Support Runbook — Scanner Jitter (SUP-77)

Applies to Product X units reporting timing jitter (see also: incident X-207).

1. Confirm firmware is Helios 4.2 or later (`GET /v2/scans/{id}` shows firmware).
2. Check operating temperature: jitter above 40C on XK-7 rev B is a known defect.
3. If rev B and temp above 40C, replace the XK-7 controller with rev C (Nordwerk part).
4. Re-run timing calibration from the Helios 4.2 menu.
5. Escalate to hardware tier only if jitter persists on rev C below 40C.

Do NOT replace the full unit: the controller swap resolves 19 of the last 20 cases.
Reference clauses: SAF-114 (hot-work permit needed for the swap), RMA-77 for parts.
