# Security Policy

## Supported
Latest `main` only (pre-1.x pace). Security fixes are released as patch versions.

## Report privately
Open a **private** report via the repo's Security tab (or email the maintainer —
never file a public issue for vulnerabilities). Include: affected endpoint/file,
reproduction steps, impact assessment. Expect acknowledgment within 72 hours.

## Known scope boundaries (by design, not oversights)
- PII redaction and injection detection are regex first-layers; Presidio +
  Rebuff-style scoring are budgeted follow-ups (see `docs/OPERATIONS.md`).
- Rate limiting is per-process; multi-replica deployments need a gateway limiter.
- Set `API_KEY` in any non-local deployment; unset means open mode.

## Hardening history
Six adversarial audit rounds are recorded in `docs/SESSION_JOURNAL.md`
(sections 6, 7, 11) with regression tests per finding (`tests/test_round4.py`, etc.).
