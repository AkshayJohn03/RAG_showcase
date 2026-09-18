# Incident Postmortem — X-207 Shutdown (INC-2091)

## Summary
Unit X-207 (Product X, XK-7 rev B, Helios 4.0) shut down at 47C during the Q3
field window. No data loss; unit replaced with rev C hardware on Helios 4.2.

## Root cause
Known rev B jitter defect above 40C (firmware_changelog Helios 4.0 entry),
compounded by missed calibration: the unit never received the Helios 4.2 update
that carries the adaptive timing fix.

## Action items
1. Push Helios 4.2 to all remaining rev B units (owner: fleet ops, due in 2 weeks).
2. Add temperature alerting at 38C (owner: firmware team).
3. Link support runbook SUP-77 from the fleet dashboard.
