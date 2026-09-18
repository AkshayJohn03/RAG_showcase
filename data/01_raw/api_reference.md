# Scanner API Reference — v2 (abridged)

## Scans endpoint
`POST /v2/scans` submits a scan job from Product X units.
Rate limit: **100 requests per minute** per API key (code **API-009** when exceeded).
Payload must include `firmware` (Helios 4.2+); older firmware returns error
`FW-410` ("firmware too old — upgrade to Helios 4.2").

## Reads endpoint
`GET /v2/scans/{id}` fetches results. Rate limit shared with POST.
Authentication: bearer API key, rotated every 90 days per SEC-301.

## Why this document exists
Dense paths (`/v2/scans`), exact codes (API-009, FW-410), and a rate number
(100/min) in one place: lexical precision matters, and the key-rotation fact
lives here while its policy lives in security_policy.md (cross-doc link).
